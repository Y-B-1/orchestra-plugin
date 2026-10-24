"""Guard gaps found by a live run of the installed plugin: the worker lease deny under a live mod, shell writes into
the engine state directory in every mode, and the pull-request push in protect."""
import io
import json
import pathlib
import shlex
import subprocess
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(HERE))

from orchestra_core.engine import Engine
from orchestra_core.guards import guard_digest
from orchestra_core.hooks import LEASE_COORDINATOR_ONLY, STATE_SHELL, main
from orchestra_core.paths import load_policy
from test_guard_plane import PlaneFixture

MODES = ('minimal', 'normal', 'protect')


class LiveFixture(PlaneFixture):
    """The run is open (a session exists) and not armed for autonomy: no lock holds."""

    def set_mode(self, mode, **policy):
        """Write the policy, then open a fresh session under it: a policy changed mid-run leaves the state unloadable."""
        (self.state / 'policy.json').write_text(json.dumps({'schema_version': 1, 'guard_mode': mode, **policy}))
        self.engine.state_path.unlink()
        self.engine = Engine(self.state, self.repo, policy=load_policy(self.state), clock=lambda: self.now[0])
        self.lease = self.engine.open_session('main')

    def live_marker(self, session='s1'):
        mods = self.root / 'xdg' / 'orchestra' / 'mods'
        mods.mkdir(parents=True, exist_ok=True)
        (mods / (session + '.json')).write_text(json.dumps({'session_id': session, 'plugin_version': '2.0.0',
                                                            'heartbeat_ms': int(time.time() * 1000),
                                                            'rules_sha256': guard_digest()}))

    def raw_call(self, command, **extra):
        payload = {'cwd': str(self.repo), 'tool_name': 'Bash', 'tool_input': {'command': command}, **extra}
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out, mock.patch('sys.stderr', new_callable=io.StringIO):
            self.assertIn(main(['PreToolUse']), (0, 2))
            return json.loads(out.getvalue()).get('hookSpecificOutput', {})

    def verdict(self, command, **extra):
        return self.raw_call(command, **extra).get('permissionDecision', 'allow')


class WorkerLeaseUnderLiveModTest(LiveFixture):
    def test_a_worker_lease_call_is_denied_while_the_mod_is_live(self):
        self.live_marker()
        command = 'python3 /x/plugins/orchestra/scripts/orchestra.py --lease L status'
        out = self.raw_call(command, session_id='s1', agent_id='a1', agent_type='orchestra:builder')
        self.assertEqual(out.get('permissionDecision'), 'deny')
        self.assertIn(LEASE_COORDINATOR_ONLY, out.get('permissionDecisionReason', ''))

    def test_the_coordinator_and_lease_free_worker_calls_still_skip(self):
        self.live_marker()
        command = 'python3 /x/plugins/orchestra/scripts/orchestra.py --lease L status'
        self.assertEqual(self.verdict(command, session_id='s1'), 'allow')
        self.assertEqual(self.verdict('git status', session_id='s1', agent_id='a1', agent_type='orchestra:builder'), 'allow')


class StateShellWriteTest(LiveFixture):
    def writes(self):
        s = shlex.quote(str(self.state))
        return ('echo x >> %s/state.json' % s, 'tee -a %s/policy.json < /dev/null' % s, 'rm %s/state.json' % s,
                'cp f %s/state.json' % s, 'sed -i s/a/b/ %s/state.json' % s, 'echo x &> %s/state.json' % s,
                'cd %s && echo x > state.json' % s)

    def reads(self):
        s = shlex.quote(str(self.state))
        return ('cat %s/state.json' % s, 'ls %s' % s, 'grep a %s/state.json 2>/dev/null' % s,
                'cat %s/state.json > /tmp/copy' % s, 'cp %s/state.json /tmp/copy' % s,
                'python3 /x/orchestra.py --actor main status %s' % s)

    def test_shell_writes_into_the_state_directory_are_denied_in_every_mode(self):
        for mode in MODES:
            self.set_mode(mode)
            for marker in (False, True):
                if marker:
                    self.live_marker()
                for command in self.writes():
                    with self.subTest(mode=mode, marker=marker, command=command):
                        out = self.raw_call(command, session_id='s1')
                        self.assertEqual(out.get('permissionDecision'), 'deny')
                        self.assertIn(STATE_SHELL, out['permissionDecisionReason'])
                        self.assertNotIn('Autonomy is active', out['permissionDecisionReason'])

    def test_reads_and_engine_commands_stay_allowed(self):
        for mode in MODES:
            self.set_mode(mode)
            for command in self.reads():
                with self.subTest(mode=mode, command=command):
                    self.assertEqual(self.verdict(command, session_id='s1'), 'allow')

    def test_a_write_outside_the_state_directory_is_untouched(self):
        for mode in MODES:
            self.set_mode(mode)
            with self.subTest(mode=mode):
                self.assertEqual(self.verdict('echo x >> /tmp/notes.txt && rm /tmp/old'), 'allow')


class ProtectBranchPushTest(LiveFixture):
    def setUp(self):
        super().setUp()
        self.set_mode('protect')
        self.branch('feature')

    def test_a_pull_request_shaped_push_is_allowed(self):
        for command in ('git push -u origin feature', 'git push origin feature', 'git push --set-upstream origin feature'):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command), 'allow')

    def test_every_other_push_stays_denied(self):
        self.git('remote', 'add', 'other', str(self.root / 'origin.git'))
        self.git('config', 'remote.other.pushurl', str(self.root / 'origin.git'))
        for command in ('git push origin main', 'git push origin ' + self.default_branch,
                        'git push origin HEAD:' + self.default_branch, 'git push --force origin feature',
                        'git push -f origin feature', 'git push origin +feature', 'git push ' + str(self.root / 'origin.git') + ' feature',
                        'git push other feature', 'git push origin feature && git status', 'git push origin nothere'):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command), 'deny')

    def test_an_unresolved_default_branch_denies(self):
        self.git('remote', 'set-head', 'origin', '-d')
        self.assertEqual(self.verdict('git push -u origin feature'), 'deny')

    def test_the_configured_release_target_is_not_a_pull_request_push(self):
        self.set_mode('protect', release={'remote': 'origin', 'target': 'feature'})
        self.assertEqual(self.verdict('git push -u origin feature'), 'deny')

    def test_the_lock_keeps_its_own_rules(self):
        self.arm()
        self.engine.disarm_autonomy()  # unattended: a kept report without a receipt
        self.assertEqual(self.verdict('git push -u origin feature'), 'deny')


if __name__ == '__main__':
    unittest.main()
