import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orchestra'
sys.path.insert(0, str(PLUGIN / 'scripts'))
import generate


class NativeTests(unittest.TestCase):
    def test_generated_agents_match_the_canonical_source(self):
        for name, content in generate.generated().items():
            self.assertEqual((PLUGIN / name).read_text(), content, name)

    def test_models_json_holds_only_the_claude_profile_with_claude_model_ids(self):
        matrix = json.loads((PLUGIN / 'config/models.json').read_text())
        self.assertEqual(set(matrix), {'schema_version', 'claude'})
        models = {sel['model'] for values in matrix['claude'].values() if values.get('selection') != 'user'
                  for sel in [values, *values.get('presets', {}).values()]}
        self.assertTrue(models <= {'claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'}, models)

    def test_role_matrix_files_and_read_only_enforcement(self):
        claude = {p.name for p in (PLUGIN / 'agents').glob('*.md')}
        self.assertEqual(claude, {f'{n}.md' for n in [
            'builder', 'builder-cleanup', 'builder-mechanical', 'code-reviewer', 'code-reviewer-medium',
            'code-reviewer-standards', 'critic', 'designer-planner',
            'investigator', 'investigator-code', 'operator', 'orchestrator']})
        read_only = ('investigator', 'critic', 'code-reviewer')
        for name in claude - {'orchestrator.md'}:
            front = (PLUGIN / 'agents' / name).read_text().split('---')[1]
            self.assertNotIn('disallowedTools', front, name)
            line = [l for l in front.splitlines() if l.startswith('tools: ')]
            self.assertEqual(len(line), 1, name)
            tools = set(line[0][len('tools: '):].split(', '))
            self.assertIn('Read', tools, name)
            self.assertFalse(tools & {'Agent', 'Task', 'Skill'}, name)
            if name.startswith(read_only):
                self.assertFalse(tools & {'Edit', 'Write', 'NotebookEdit'}, name)

    def test_generate_refuses_bad_tool_allowlists(self):
        roles = json.loads((PLUGIN / 'config/roles.json').read_text())
        cases = [('critic', 'tools', ['Read', 'Edit'], 'read-only role lists a write tool'),
                 ('builder', 'tools', ['Read', 'Agent(Explore)'], 'workers never delegate'),
                 ('investigator', 'preset_tools', {'code': ['Read', 'Task']}, 'workers never delegate'),
                 ('operator', 'tools', [], 'non-empty tools allowlist')]
        for role_id, key, value, message in cases:
            changed = json.loads(json.dumps(roles))
            next(r for r in changed['roles'] if r['id'] == role_id)[key] = value
            with self.subTest(role_id), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'orchestra'
                shutil.copytree(PLUGIN, root, ignore=shutil.ignore_patterns('agents', '__pycache__'))
                (root / 'config/roles.json').write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, message):
                    generate.generated(root)

    def test_standards_preset_is_sonnet_medium_variant_file(self):
        path = PLUGIN / 'agents/code-reviewer-standards.md'
        self.assertTrue(path.exists())
        front = path.read_text().split('---')[1]
        self.assertIn('model: claude-sonnet-5-5\n', front)
        self.assertIn('effort: medium\n', front)
        desc = [l for l in front.splitlines() if l.startswith('description:')][0]
        self.assertIn('Lens: standards', desc)

    def test_reviewer_size_variants_are_generated(self):
        for name, model, effort in (('medium', 'claude-sonnet-5-5', 'medium'),):
            with self.subTest(name):
                front = (PLUGIN / f'agents/code-reviewer-{name}.md').read_text().split('---')[1]
                self.assertIn(f'name: code-reviewer-{name}\n', front)
                self.assertIn(f'model: {model}\n', front)
                self.assertIn(f'effort: {effort}\n', front)
                desc = [l for l in front.splitlines() if l.startswith('description:')][0]
                self.assertIn('Lens: combined', desc)

    def test_reviewer_size_variants_keep_the_reviewer_tools(self):
        for name in ('medium',):
            with self.subTest(name):
                front = (PLUGIN / f'agents/code-reviewer-{name}.md').read_text().split('---')[1]
                line = [l for l in front.splitlines() if l.startswith('tools: ')][0]
                self.assertEqual(set(line[len('tools: '):].split(', ')), {'Read', 'Bash'})

    def test_claude_repair_preset_is_override_dispatch_with_no_variant_file(self):
        matrix = json.loads((PLUGIN / 'config/models.json').read_text())['claude']
        self.assertEqual(matrix['builder']['presets']['repair']['dispatch'], 'override')
        self.assertFalse((PLUGIN / 'agents/builder-repair.md').exists())

    def test_claude_variant_descriptions_name_their_mode(self):
        def desc(name):
            line = [l for l in (PLUGIN / 'agents' / name).read_text().split('---')[1].splitlines()
                    if l.startswith('description:')][0]
            return json.loads(line.split(':', 1)[1])
        for base, variant, mode in [('investigator-code', 'investigator', 'Mode: code.'),
                                    ('builder-mechanical', 'builder', 'Mode: mechanical.'),
                                    ('builder-cleanup', 'builder', 'Mode: cleanup.')]:
            self.assertIn(mode, desc(base + '.md'))
            self.assertIn(desc(variant + '.md'), desc(base + '.md'))
            self.assertNotEqual(desc(base + '.md'), desc(variant + '.md'))

    def test_orchestrator_follows_the_user_selection(self):
        front = (PLUGIN / 'agents/orchestrator.md').read_text().split('---')[1]
        self.assertNotIn('model:', front)
        self.assertNotIn('effort:', front)
        self.assertIn('skills: [orchestra]\n', front)
        self.assertNotIn('disallowedTools', front)
        self.assertNotIn('tools:', front)

    def test_generate_refuses_unresolved_preload_skill_and_missing_mode_file(self):
        def copy_plugin(temp):
            copy = Path(temp) / 'orchestra'
            shutil.copytree(PLUGIN, copy, ignore=shutil.ignore_patterns('__pycache__'))
            return copy

        cases = {
            'unresolved skill name': (lambda c: shutil.rmtree(c / 'skills/orchestra-operate'), 'orchestra-operate'),
            'preload blocked by disable-model-invocation': (
                lambda c: (c / 'skills/orchestra-worker/SKILL.md').write_text(
                    '---\nname: orchestra-worker\ndescription: x\ndisable-model-invocation: true\n---\nbody\n'),
                'disable-model-invocation'),
            'declared mode without a file': (lambda c: (c / 'skills/orchestra-build/references/cleanup.md').unlink(),
                                            'cleanup'),
        }
        for label, (damage, needle) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as temp:
                copy = copy_plugin(temp)
                damage(copy)
                with self.assertRaises(ValueError) as caught:
                    generate.generated(root=copy)
                self.assertIn(needle, str(caught.exception))
                result = subprocess.run([sys.executable, str(copy / 'scripts/generate.py'), '--check'],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Generate refused', result.stderr)

    def test_manifest_versions_are_equal(self):
        versions = {
            name: json.loads((ROOT / name).read_text())['version']
            for name in ['plugins/orchestra/plugin.json', 'plugins/orchestra/.claude-plugin/plugin.json']
        }
        market = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        entry = next(p for p in market['plugins'] if p['name'] == 'orchestra')
        # Claude Code takes the version from plugin.json first; a second copy in the entry can only drift.
        self.assertNotIn('version', entry)
        self.assertEqual(len(set(versions.values())), 1, versions)
        self.assertEqual(set(versions.values()), {'2.15.3'})

    def test_2152_docs_describe_the_release(self):
        changelog = (ROOT / 'CHANGELOG.md').read_text().split('## 2.15.2')[1].split('\n## ')[0]
        notes = (ROOT / 'docs/release-notes/v2.15.2.md').read_text()
        ledger = (ROOT / 'docs/BUILD-LEDGER.md').read_text().split('## 2.15.2')[1]
        for label, text in (('changelog', changelog), ('notes', notes), ('ledger', ledger)):
            for word in ('model_fit', 'replace', 'resume', 'full_check', 'deferred', 'F108'):
                with self.subTest(label, word=word):
                    self.assertIn(word, text)
        self.assertIn('t1', ledger)
        self.assertIn('22 scenarios', ledger)
        self.assertIn('`cancelBoardTimer` is used', (ROOT / 'docs/BUILD-LEDGER.md').read_text())

    def test_2153_docs_describe_the_release(self):
        changelog = (ROOT / 'CHANGELOG.md').read_text().split('## 2.15.3')[1].split('\n## ')[0]
        notes = (ROOT / 'docs/release-notes/v2.15.3.md').read_text()
        ledger = (ROOT / 'docs/BUILD-LEDGER.md').read_text().split('## 2.15.3')[1]
        for label, text in (('changelog', changelog), ('notes', notes), ('ledger', ledger)):
            for word in ('track', 'overlaps', 'set-default', 'live-gh-wizard', 'Known gaps'):
                with self.subTest(label, word=word):
                    self.assertIn(word, text)
        for word in ('F112', 'F114', 'N4', 'L2', 'l3'):
            with self.subTest('ledger', word=word):
                self.assertIn(word, ledger)
        cli = (ROOT / 'docs/cli.md').read_text()
        self.assertIn('Changes in 2.15.3', cli)
        self.assertIn('2.15.3 additions', (PLUGIN / 'skills/orchestra/references/cli.md').read_text())

    def test_2151_doc_notes_are_corrected(self):
        ledger = (ROOT / 'docs/BUILD-LEDGER.md').read_text()
        self.assertNotIn('still allows `rm -rf /tmp/*`', ledger)
        cli = (ROOT / 'docs/cli.md').read_text()
        self.assertNotIn('open_session', cli)
        self.assertIn('only when the card was parked without', cli)
        for word in ('model_fit', '`replace OLD TASKFILE`', '`resume ID`', 'full_check', 'needs_triage', 'Changes in 2.15.2'):
            self.assertIn(word, cli)

    def test_plugin_has_a_square_icon(self):
        icon = PLUGIN / '.claude-plugin/icon.png'
        data = icon.read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        width, height = int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
        self.assertEqual(width, height)
        self.assertTrue(512 <= width <= 2048 and len(data) < 2_000_000)

    def test_prepr_reviewer_agents_exist(self):
        sys.path.insert(0, str(PLUGIN / 'scripts'))
        from orchestra_core.engine import REVIEWER_BAND, REVIEWER_FULL
        for agent in (REVIEWER_BAND[-1], REVIEWER_FULL[-1]):
            with self.subTest(agent):
                self.assertTrue(agent.startswith('orchestra:'))
                self.assertTrue((PLUGIN / 'agents' / (agent[len('orchestra:'):] + '.md')).is_file())

    def test_changelog_first_heading_matches_version(self):
        version = json.loads((PLUGIN / 'plugin.json').read_text())['version']
        heading = next(line for line in (ROOT / 'CHANGELOG.md').read_text().splitlines() if line.startswith('## '))
        self.assertTrue(heading[3:].startswith(version), heading)

    def test_mod_files_exist(self):
        claude = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
        self.assertEqual(claude['hooks'], ['./hooks/claude.json', './hooks/mods.json'])
        self.assertEqual(claude['types'], './types/index.d.ts')
        self.assertEqual(json.loads((PLUGIN / 'hooks/mods.json').read_text()), {'modules': ['./mod/orchestra.ts']})
        for name in ['hooks/mod/orchestra.ts', 'hooks/mod/marker.ts', 'types/index.d.ts']:
            self.assertTrue((PLUGIN / name).is_file(), name)

    def test_relaunch_harness_is_removed(self):
        self.assertFalse((PLUGIN / 'config/relaunch-prompt.md').exists())
        self.assertFalse((PLUGIN / 'scripts/orchestra_core/relaunch.py').exists())


if __name__ == '__main__':
    unittest.main()
