"""The parallel-waves checkpoint: `waves`, `wave`, the lone-start refusal and the lease-free `board --view`."""
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import DEFAULT, GUARD_MODES, POLICY_KEYS, Engine, EngineError, _digest

CLI = SCRIPTS / 'orchestra.py'


class WaveFixture(te.EngineFixture):
    def engine_with(self, policy=None, **session):
        """A fresh state directory with its own policy and run size."""
        self.engine = Engine(self.root / ('state-%d' % time.monotonic_ns()), self.repo, policy)
        self.lease = self.engine.open_session('main', **session)

    def progress(self):
        path = self.engine.state_dir / 'progress.md'
        return path.read_text() if path.exists() else ''


class WavesReadTests(WaveFixture):
    def test_overlaps_chains_and_layers(self):
        self.task('a')
        self.task('b')
        self.task('c', files=['a'])
        self.task('d', dependencies=['b'])
        out = self.engine.waves()
        self.assertEqual(out['overlaps'], [['a', 'c']])
        self.assertEqual(out['chains']['d'], {'dependencies': ['b'], 'review_of': []})
        self.assertEqual(out['waves'], [['a', 'b'], ['c'], ['d']])
        self.assertEqual(out['startable_now'], ['a', 'b', 'c'])
        self.assertEqual(out['blocked'], [])

    def test_a_builder_without_files_overlaps_every_editing_card(self):
        self.task('a')
        self.task('b')
        self.task('whole', files=[])
        out = self.engine.waves()
        self.assertEqual(out['overlaps'], [['a', 'whole'], ['b', 'whole']])
        self.assertEqual(out['waves'], [['a', 'b'], ['whole']])

    def test_repair_chain_files_count_as_reservation(self):
        self.task('orig', files=['x'])
        self.task('other', files=['x/inner'])
        self.assertEqual(self.engine.waves()['overlaps'], [['orig', 'other']])

    def test_a_parked_prerequisite_blocks_its_dependents(self):
        self.task('a')
        self.task('b', dependencies=['a'])
        self.task('c', dependencies=['b'])
        self.task('free')
        self.engine.park('main', self.lease, 'a', 'waiting for the owner')
        out = self.engine.waves()
        self.assertEqual(out['blocked'], ['b', 'c'])
        self.assertEqual(out['waves'], [['free']])

    def test_waves_are_cut_to_the_worker_and_worktree_caps(self):
        self.engine_with(dict(schema_version=1, max_workers=2))
        for name in 'abc':
            self.task(name)
        self.assertEqual(self.engine.waves()['waves'], [['a', 'b'], ['c']])
        self.engine_with(dict(schema_version=1, max_worktrees=1))
        for name in 'abc':
            self.task(name)
        self.assertEqual(self.engine.waves()['waves'], [['a'], ['b'], ['c']])

    def test_startable_now_runs_the_real_start_checks(self):
        self.engine_with(size='tiny')
        self.task('t1')
        self.task('rv', role='code-reviewer', mode='final', review_of=['t1'], files=[])
        self.task('dep', dependencies=['t1'])
        out = self.engine.waves()
        self.assertEqual(out['startable_now'], ['t1'])  # a tiny builder starts inline; the reviewer waits for a report
        self.engine.start_inline('main', self.lease, 't1')
        self.assertNotIn('t1', self.engine.waves()['startable_now'])


class CheckpointTests(WaveFixture):
    def test_a_lone_dispatch_is_refused_when_another_disjoint_card_could_start(self):
        self.task('a')
        self.task('b')
        with self.assertRaisesRegex(EngineError, r'Start the whole wave: wave .*\ba\b.*\bb\b'):
            self.engine.dispatch('main', self.lease, 'a', 'w')
        with self.assertRaisesRegex(EngineError, 'Start the whole wave'):
            self.engine.start_inline('main', self.lease, 'a')
        with self.assertRaisesRegex(EngineError, 'Start the whole wave'):
            self.engine.wave('main', self.lease, ['a'])
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'queued')

    def test_no_refusal_for_one_startable_card_overlap_or_full_capacity(self):
        self.task('a')
        self.task('c', files=['a'])
        self.task('d', dependencies=['a'])
        self.engine.dispatch('main', self.lease, 'a', 'w')  # c overlaps, d waits: a is alone
        self.engine_with(dict(schema_version=1, max_workers=1))
        self.task('a')
        self.task('b')
        self.engine.dispatch('main', self.lease, 'a', 'w')  # one worker slot, so no pairing is startable
        self.engine_with(dict(schema_version=1, max_worktrees=1))
        self.task('x')
        self.task('a')
        self.task('b')
        self.engine.start_inline('main', self.lease, 'x', serial='holds the inline slot')
        self.engine.dispatch('main', self.lease, 'a', 'w')  # a pair would need two worktrees and the inline slot is taken
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'running')

    def test_the_refusal_uses_the_inline_slot_to_save_a_worktree(self):
        self.engine_with(dict(schema_version=1, max_worktrees=1))
        self.task('a')
        self.task('b')
        with self.assertRaisesRegex(EngineError, 'wave --inline a b'):
            self.engine.dispatch('main', self.lease, 'b', 'w')

    def test_two_tiny_cards_cannot_pair_because_both_must_be_inline(self):
        self.engine_with(size='tiny')
        self.task('a')
        self.task('b')
        self.engine.start_inline('main', self.lease, 'a')

    def test_serial_reason_overrides_and_is_logged_after_the_write(self):
        self.task('a')
        self.task('b')
        with self.assertRaisesRegex(EngineError, '--serial'):
            self.engine.dispatch('main', self.lease, 'a', 'w', serial='  ')
        self.assertEqual(self.progress(), '')
        self.engine.dispatch('main', self.lease, 'a', 'w', serial='b needs the result of a')
        self.assertIn('b needs the result of a', self.progress())

    def test_a_failed_serial_start_logs_nothing(self):
        self.task('a')
        self.task('c', files=['a'])
        self.engine.dispatch('main', self.lease, 'a', 'w')
        with self.assertRaises(EngineError):
            self.engine.dispatch('main', self.lease, 'c', 'w2', serial='nothing to log')
        self.assertEqual(self.progress(), '')

    def test_parallel_waves_false_disables_the_refusal(self):
        self.engine_with(dict(schema_version=1, parallel_waves=False))
        self.task('a')
        self.task('b')
        self.engine.dispatch('main', self.lease, 'a', 'w')

    def test_parallel_waves_is_a_policy_key_but_not_a_default(self):
        self.assertIn('parallel_waves', POLICY_KEYS)
        self.assertNotIn('parallel_waves', DEFAULT)
        for bad in ('yes', 1, None):
            with self.assertRaisesRegex(EngineError, 'parallel_waves'):
                Engine(self.root / 'x', self.repo, dict(schema_version=1, parallel_waves=bad))
        engine = Engine(self.root / 'y', self.repo)  # the default hash must not move, or every running run would mismatch
        self.assertEqual(engine.policy_hash, _digest(dict(policy=DEFAULT, contracts=engine.contract_hash)))


class WaveCommandTests(WaveFixture):
    def test_wave_starts_every_card_together(self):
        self.task('a')
        self.task('b')
        out = self.engine.wave('main', self.lease, ['a', 'b'])
        self.assertEqual(set(out['assignments']), {'a', 'b'})
        self.assertIsNone(out['inline'])
        tasks = self.engine.status()['tasks']
        self.assertEqual([tasks[i]['state'] for i in 'ab'], ['running', 'running'])
        self.assertEqual([tasks[i]['worker'] for i in 'ab'], ['orchestra-a', 'orchestra-b'])
        self.assertEqual(tasks['a']['assignment'], out['assignments']['a'])

    def test_wave_with_one_inline_card(self):
        self.task('a')
        self.task('b')
        out = self.engine.wave('main', self.lease, ['a', 'b'], inline='a')
        self.assertEqual(out['inline'], 'a')
        tasks = self.engine.status()['tasks']
        self.assertEqual((tasks['a']['inline'], tasks['a']['worker']), (True, 'main'))
        self.assertFalse(tasks['b']['inline'])

    def test_wave_is_all_or_nothing(self):
        self.task('a')
        self.task('b')
        self.task('c', files=['a'])
        for ids, inline in ((['a', 'b', 'c'], None), (['a', 'b', 'missing'], None), (['a', 'a'], None), (['a', 'b'], 'zz')):
            with self.assertRaises(EngineError, msg=ids):
                self.engine.wave('main', self.lease, ids, inline=inline)
        self.assertEqual({t['state'] for t in self.engine.status()['tasks'].values()}, {'queued'})

    def test_wave_refuses_a_review_card_inline_and_an_empty_list(self):
        self.task('a')
        self.task('b')
        self.task('built')
        self.engine.dispatch('main', self.lease, 'built', 'wb', serial='setup')
        self.engine.report('wb', self.engine.status()['tasks']['built']['assignment'], te.done())
        self.task('rv', role='code-reviewer', mode='final', review_of=['built'], files=[])
        with self.assertRaisesRegex(EngineError, 'review'):
            self.engine.wave('main', self.lease, ['a', 'rv'], inline='rv')
        with self.assertRaises(EngineError):
            self.engine.wave('main', self.lease, [])

    def test_wave_needs_the_lease(self):
        self.task('a')
        self.task('b')
        with self.assertRaises(EngineError):
            self.engine.wave('main', 'wrong', ['a', 'b'])


class BoardViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='waves view ')
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.repo, self.state = root / 'repo', root / 'state'
        self.repo.mkdir()
        for args in (['init', '-q', '-b', 'main'], ['config', 'user.email', 't@example.invalid'], ['config', 'user.name', 'T']):
            subprocess.check_call(['git', '-C', str(self.repo), *args])
        (self.repo / 'a').write_text('x')
        subprocess.check_call(['git', '-C', str(self.repo), 'add', 'a'])
        subprocess.check_call(['git', '-C', str(self.repo), 'commit', '-qm', 'i'])
        self.root = root
        self.lease = self.cli('start', '--size', 'medium', '--harness-session', 'SECRET-SESSION-ID')['lease']

    def cli(self, *args, lease=False, expected=0):
        cmd = [sys.executable, str(CLI), '--repo', str(self.repo), '--state', str(self.state)]
        if lease:
            cmd += ['--lease', self.lease]
        result = subprocess.run(cmd + list(args), capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return json.loads(result.stdout if expected == 0 else result.stderr)

    def add(self, name, **kw):
        task = dict(id=name, role='builder', mode='implementation', inputs=['spec'], acceptance=['ok'], files=[name],
                    resources=[], dependencies=[])
        task.update(kw)
        path = self.root / (name + '.json')
        path.write_text(json.dumps(task))
        self.cli('add', str(path), lease=True)

    def test_view_is_cheap_allowlisted_and_never_leaks_credentials(self):
        self.add('a')
        self.add('b')
        self.add('c', dependencies=['a'])
        started = self.cli('wave', 'a', 'b', '--helper', 'fixture helper', lease=True)
        started_c = json.dumps(started)
        t0 = time.monotonic()
        view = self.cli('board', '--view', '--session', 'SECRET-SESSION-ID')
        self.assertLess(time.monotonic() - t0, 2)
        text = json.dumps(view)
        for secret in (self.lease, 'SECRET-SESSION-ID', *started['assignments'].values()):
            self.assertNotIn(secret, text)
        self.assertNotIn('"assignment"', text)
        self.assertNotIn('"lease"', text)
        self.assertNotIn('harness_session', text)
        self.assertEqual(view['session'], {'active': True, 'size': 'medium'})
        self.assertIs(view['bound'], True)
        self.assertIs(self.cli('board', '--view', '--session', 'other')['bound'], False)
        self.assertIs(self.cli('board', '--view')['bound'], False)
        self.assertEqual(view['autonomy'], {'active': False})
        self.assertEqual(view['counts']['running'], 2)
        self.assertIn('running', view['counts_note'])
        self.assertEqual(view['columns']['running'], ['a', 'b'])
        self.assertEqual(view['columns']['queued'], ['c'])
        cards = {c['id']: c for c in view['cards']}
        self.assertEqual(cards['c']['deps_open'], ['a'])
        self.assertEqual(cards['a']['worker'], 'orchestra-a')
        self.assertEqual(view['guard_mode'], 'minimal')
        self.assertEqual(view['startable_now'], [])
        self.assertEqual(view['pull_requests'], [])
        self.assertIsNone(view['latest_review'])
        self.assertIsNone(view['latest_gate'])
        self.assertTrue(started_c)

    def test_plain_board_is_unchanged(self):
        self.add('a')
        self.assertEqual(self.cli('board'), {'builder': {'queued': ['a']}})

    def test_waves_command_and_cli_checkpoint(self):
        self.add('a')
        self.add('b')
        out = self.cli('waves')
        self.assertEqual(out['startable_now'], ['a', 'b'])
        err = self.cli('dispatch', 'a', '--helper', 'x', lease=True, expected=2)
        self.assertIn('Start the whole wave: wave', err['error'])
        ok = self.cli('dispatch', 'a', '--helper', 'x', '--serial', 'b waits on a', lease=True)
        self.assertEqual(ok['task'], 'a')
        self.assertIn('b waits on a', (self.state / 'progress.md').read_text())

    def test_where_reports_the_guard_mode(self):
        self.assertEqual(self.cli('where')['guard_mode'], 'minimal')
        (self.state / 'policy.json').write_text(json.dumps(dict(schema_version=1, guard_mode='protect')))
        self.assertEqual(self.cli('where')['guard_mode'], 'protect')


class GuardModeTests(unittest.TestCase):
    def test_guard_modes_include_minimal(self):
        self.assertEqual(GUARD_MODES, ('minimal', 'normal', 'protect'))


if __name__ == '__main__':
    unittest.main()
