"""EMIT: the `card` brief renderer and `wave --emit` (agent types, prompts and agent() calls written from engine facts)."""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core import briefs
from orchestra_core.engine import EngineError

CLI = SCRIPTS / 'orchestra.py'
CONFIG = SCRIPTS.parent / 'config'


def variant_types():
    """Every agent type the plugin ships, derived from models.json (never listed by hand): the role itself, plus
    `role-preset` for each preset whose model or effort differs from the role and is not a dispatch override."""
    models = json.loads((CONFIG / 'models.json').read_text())['claude']
    roles = json.loads((CONFIG / 'roles.json').read_text())['roles']
    types = {}
    for role in roles:
        if role['id'] == 'orchestrator':
            continue
        matrix = models[role['id']]
        names = {role['id']}
        for name, values in matrix.get('presets', {}).items():
            if (values['model'], values['effort']) != (matrix['model'], matrix['effort']) and values.get('dispatch') != 'override':
                names.add(role['id'] + '-' + name)
        types[role['id']] = {'orchestra:' + n for n in names}
    return types, models, roles


class CliFixture(te.EngineFixture):
    def cli(self, *args, expected=0, lease=True):
        cmd = [sys.executable, str(CLI), '--repo', str(self.repo), '--state', str(self.engine.state_dir)]
        if lease:
            cmd += ['--lease', self.lease]
        result = subprocess.run(cmd + list(args), capture_output=True, text=True, timeout=60)
        self.assertEqual(expected, result.returncode, result.stderr + result.stdout)
        return json.loads(result.stdout if expected == 0 else result.stderr)

    def head(self):
        return self.git('rev-parse', 'HEAD')


class CardRenderTests(CliFixture):
    def setUp(self):
        super().setUp()
        self.task('a', outcome='Ship the a feature', inputs=['spec.md', 'the base commit'],
                  acceptance=['first criterion holds', 'second criterion holds'], files=['a'], resources=['port 4100'])

    def test_card_prints_the_brief_skeleton(self):
        text = self.cli('card', 'a', lease=False)['brief']
        self.assertRegex(text, r'(?m)^Mode: implementation$')
        self.assertIn('Ship the a feature', text)
        self.assertIn('spec.md', text)
        self.assertIn('- a', text)  # ownership: files
        self.assertIn('port 4100', text)  # ownership: resources
        self.assertRegex(text, r'(?m)^1\. first criterion holds$')
        self.assertRegex(text, r'(?m)^2\. second criterion holds$')
        self.assertRegex(text, r'(?m)^## Keep$')
        self.assertRegex(text, r'(?m)^## Remove$')
        self.assertIn(str(briefs.PACKAGE_ROOT), text)
        self.assertIn(self.head(), text)
        self.assertRegex(text, r'(?m)^STATUS: PASS\|ISSUES\|BLOCKED$')
        skeleton = next(line for line in text.splitlines() if line.startswith('SELF_REVIEW: '))
        criteria = json.loads(skeleton[len('SELF_REVIEW: '):])['criteria']
        self.assertEqual(['first criterion holds', 'second criterion holds'], [c['criterion'] for c in criteria])

    def test_card_is_lease_free_and_read_only(self):
        before = json.loads(self.engine.state_path.read_text())
        self.cli('card', 'a', lease=False)
        self.assertEqual(before, json.loads(self.engine.state_path.read_text()))
        self.assertEqual('', self.git('status', '--porcelain'))

    def test_a_reviewer_brief_has_no_keep_or_remove(self):
        self.task('rv', role='code-reviewer', mode='final', review_of=['a'], files=[])
        text = self.cli('card', 'rv', lease=False)['brief']
        self.assertRegex(text, r'(?m)^Mode: final$')
        self.assertNotIn('## Keep', text)

    def test_out_writes_the_file_and_the_engine_accepts_it_as_a_brief(self):
        out = self.root / 'a-brief.md'
        result = self.cli('card', 'a', '--out', str(out), lease=False)
        self.assertEqual(str(out.resolve()), result['path'])
        self.assertEqual(self.cli('card', 'a', lease=False)['brief'], out.read_text())
        self.task('b', brief=str(out), files=['b'])  # _check_contract and the Keep/Remove check pass
        self.assertEqual(str(out), self.engine.status()['tasks']['b']['brief'])

    def test_an_unknown_card_is_refused(self):
        self.assertIn('Unknown task', self.cli('card', 'nope', expected=2, lease=False)['error'])


class AgentTypeTests(unittest.TestCase):
    def test_every_role_and_mode_maps_to_a_shipped_agent_type_derived_from_the_config(self):
        types, models, roles = variant_types()
        seen = set()
        for role in roles:
            if role['id'] == 'orchestrator':
                continue
            for mode in role['modes']:
                agent_type, override = briefs.dispatch_for({'role': role['id'], 'mode': mode})
                self.assertIn(agent_type, types[role['id']], (role['id'], mode))
                seen.add(agent_type)
                preset = models[role['id']].get('presets', {}).get(mode, {})
                if preset.get('dispatch') == 'override':
                    self.assertEqual(preset['model'], override)  # the repair card keeps the base agent and overrides the model
                    self.assertEqual('orchestra:' + role['id'], agent_type)
                else:
                    self.assertIsNone(override)
        self.assertTrue({'orchestra:builder-mechanical', 'orchestra:investigator-code'} <= seen)

    def test_a_lens_variant_selects_the_reviewer_preset_and_an_unknown_one_is_refused(self):
        types, _, _ = variant_types()
        for lens, name in (('standards', 'orchestra:code-reviewer-standards'), ('medium', 'orchestra:code-reviewer-medium')):
            self.assertEqual((name, None), briefs.dispatch_for({'role': 'code-reviewer', 'mode': 'final', 'variant': lens}))
            self.assertIn(name, types['code-reviewer'])
        with self.assertRaises(EngineError):
            briefs.dispatch_for({'role': 'code-reviewer', 'mode': 'final', 'variant': 'nonsense'})


class WaveEmitTests(CliFixture):
    def test_emit_prints_one_object_per_card_with_the_exact_prompt(self):
        types, _, _ = variant_types()
        self.task('a', outcome='Do a')
        self.task('m', mode='mechanical')
        self.task('i', role='investigator', mode='code', files=[])
        self.task('c', role='critic', mode='judge', files=[])
        base = self.head()
        result = self.cli('wave', 'a', 'm', 'i', 'c', '--emit')
        emitted = {e['task']: e for e in result['emit']}
        self.assertEqual({'a', 'm', 'i', 'c'}, set(emitted))
        state = self.engine.state_dir
        for task_id, entry in emitted.items():
            role = self.engine.status()['tasks'][task_id]['role']
            self.assertIn(entry['agent_type'], types[role])
            self.assertIsNone(entry['model_override'])
            self.assertEqual(result['workers'][task_id], entry['worker'])
            self.assertEqual(result['assignments'][task_id], entry['token'])
            brief = pathlib.Path(entry['brief'])
            self.assertEqual(state / 'briefs', brief.parent)
            self.assertRegex(brief.read_text(), r'(?m)^Mode: ' + re.escape(self.engine.status()['tasks'][task_id]['mode']) + '$')
            self.assertIn('Assignment: %s %s' % (entry['worker'], entry['token']), entry['prompt'])
            self.assertIn(entry['brief'], entry['prompt'])
            self.assertTrue(entry['agent_call'].startswith('agent(' + json.dumps(entry['prompt'])), entry['agent_call'])
            self.assertIn("agentType: '%s'" % entry['agent_type'], entry['agent_call'])
        self.assertEqual('orchestra:builder-mechanical', emitted['m']['agent_type'])
        self.assertEqual('orchestra:investigator-code', emitted['i']['agent_type'])
        self.assertEqual('worktree', emitted['a']['isolation'])  # concurrent editors each get a worktree
        self.assertIsNone(emitted['c']['isolation'])
        self.assertEqual('git merge --ff-only ' + base, emitted['a']['fast_forward'])
        self.assertIn(emitted['a']['fast_forward'], emitted['a']['prompt'])
        self.assertIn("isolation: 'worktree'", emitted['a']['agent_call'])

    def test_an_inline_card_gets_a_brief_but_no_agent_call(self):
        self.task('a')
        self.task('b')
        result = self.cli('wave', '--inline', 'a', 'b', '--emit')
        emitted = {e['task']: e for e in result['emit']}
        self.assertTrue(emitted['a']['inline'])
        self.assertNotIn('agent_call', emitted['a'])
        self.assertTrue(pathlib.Path(emitted['a']['brief']).is_file())
        self.assertIn('agent_call', emitted['b'])

    def test_a_card_whose_brief_lost_its_mode_line_cannot_be_emitted_and_nothing_starts(self):
        brief = self.root / 'b.md'
        brief.write_text('Mode: implementation\n\n## Keep\nx\n\n## Remove\nnone\n')
        self.task('a', brief=str(brief))
        brief.write_text('no mode here\n## Keep\n## Remove\n')
        error = self.cli('wave', 'a', '--emit', expected=2)['error']
        self.assertIn('Mode: implementation', error)
        self.assertEqual('queued', self.engine.status()['tasks']['a']['state'])

    def test_a_card_with_its_own_brief_is_emitted_with_that_file(self):
        brief = self.root / 'own.md'
        brief.write_text('Mode: implementation\n\n## Keep\nx\n\n## Remove\nnone\n')
        self.task('a', brief=str(brief))
        entry = self.cli('wave', 'a', '--emit')['emit'][0]
        self.assertEqual(str(brief), entry['brief'])

    def test_a_repair_card_carries_the_model_override(self):
        self.assertEqual(('orchestra:builder', 'claude-opus-5-5'), briefs.dispatch_for({'role': 'builder', 'mode': 'repair'}))

    def test_wave_without_emit_has_no_emit_key(self):
        self.task('a')
        self.assertNotIn('emit', self.cli('wave', 'a', '--serial', 'fixture: one card'))


class LinkedWorktreeCliTests(unittest.TestCase):
    """F7: the CLI run from a linked worktree whose own state is empty while the main checkout has a run."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='linked cli ')
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name).resolve()
        self.main, self.linked = self.root / 'main checkout', self.root / 'linked checkout'
        self.main.mkdir()
        self.git(self.main, 'init', '-q', '-b', 'main')
        self.git(self.main, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '-q', '--allow-empty', '-m', 'init')
        self.git(self.main, 'worktree', 'add', '-q', str(self.linked), '-b', 'side')
        self.xdg = self.root / 'xdg'
        self.env = {**os.environ, 'XDG_STATE_HOME': str(self.xdg)}
        self.env.pop('ORCHESTRA_STATE_DIR', None)

    @staticmethod
    def git(cwd, *args):
        return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()

    def cli(self, repo, *args):
        return subprocess.run([sys.executable, str(CLI), '--repo', str(repo), *args], env=self.env, capture_output=True,
                              text=True, timeout=60)

    def state_files(self):
        return sorted(str(p) for p in (self.xdg / 'orchestra').rglob('*')) if (self.xdg / 'orchestra').exists() else []

    def test_a_linked_worktree_without_state_is_refused_when_the_main_checkout_has_a_run(self):
        self.assertEqual(0, self.cli(self.main, 'start', '--size', 'tiny').returncode)
        before = self.state_files()
        for command in (['board'], ['status'], ['waves']):
            result = self.cli(self.linked, *command)
            self.assertEqual(2, result.returncode, (command, result.stdout, result.stderr))
            self.assertIn(str(self.main), json.loads(result.stderr)['error'])
            self.assertEqual('', result.stdout)
        self.assertEqual(before, self.state_files())  # no state directory and no state.lock was created

    def test_nothing_changes_inside_the_main_checkout_or_without_a_main_run(self):
        self.assertEqual({}, json.loads(self.cli(self.linked, 'board').stdout))  # no run anywhere: not refused
        self.assertEqual(0, self.cli(self.main, 'start', '--size', 'tiny').returncode)
        self.assertEqual(0, self.cli(self.main, 'board').returncode)
        self.assertEqual(0, self.cli(self.linked, 'where').returncode)  # where only reports locations

    def test_an_explicit_state_directory_is_not_refused(self):
        self.assertEqual(0, self.cli(self.main, 'start', '--size', 'tiny').returncode)
        own = self.root / 'own state'
        self.assertEqual(0, self.cli(self.linked, '--state', str(own), 'board').returncode)


if __name__ == '__main__':
    unittest.main()
