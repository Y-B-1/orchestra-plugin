"""`do` runs several coordinator commands in one call, in order, and stops at the first refusal; every lease command
refreshes <state>/NOW.md; `finish --accept-reported` accepts what it can before closing."""
import json
import pathlib
import shlex
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te


class DoTests(te.EngineFixture):
    def cli(self, *args):
        return te.run_cli(self, '--lease', self.lease, *args)

    def built(self, name):
        (self.repo / name).write_text(name)
        self.git('add', name)
        self.git('commit', '-qm', name)
        self.task(name)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, te.done('Built ' + name))

    def test_do_runs_each_step_in_order_and_returns_each_result(self):
        self.built('B1')
        self.built('B2')
        code, out, err = self.cli('do', 'accept B1', 'accept B2')
        self.assertEqual(0, code, err)
        body = json.loads(out)
        self.assertEqual(['accept B1', 'accept B2'], [s['step'] for s in body['steps']])
        self.assertEqual(['B1', 'B2'], [s['result']['accepted'] for s in body['steps']])
        self.assertEqual(['accepted', 'accepted'], [self.engine.status()['tasks'][i]['state'] for i in ('B1', 'B2')])

    def test_do_stops_at_the_first_refusal_and_keeps_earlier_steps(self):
        self.built('B1')
        code, out, err = self.cli('do', 'accept B1', 'accept NOPE', 'accept B1')
        self.assertEqual(2, code)
        body = json.loads(out)
        self.assertEqual(['accept B1'], [s['step'] for s in body['steps']])
        self.assertEqual('accept NOPE', body['refused']['step'])
        self.assertTrue(body['refused']['error'])
        self.assertEqual('accepted', self.engine.status()['tasks']['B1']['state'])

    def test_do_refuses_a_nested_do_start_or_a_global_option(self):
        for step in ('do accept B1', 'start --size small', '--lease x accept B1', 'accept B1 --repo /tmp'):
            with self.subTest(step=step):
                code, out, err = self.cli('do', step)
                self.assertEqual(2, code)
                self.assertIn('error', json.loads(out)['refused'])

    def test_a_step_missing_a_required_flag_gives_json_only_with_the_parser_message(self):
        code, out, err = self.cli('do', 'cancel B1')
        self.assertEqual(2, code)
        body = json.loads(out)  # stdout is the JSON alone: no usage text before it
        self.assertEqual('cancel B1', body['refused']['step'])
        self.assertIn('--reason', body['refused']['error'])

    def test_a_lease_command_refreshes_now_md(self):
        now = self.engine.state_dir / 'NOW.md'
        self.assertFalse(now.exists())
        self.task('Q1')
        code, out, err = self.cli('do', 'park Q1 --reason ' + shlex.quote('needs-owner: an API key'))
        self.assertEqual(0, code, err)
        self.assertIn('Q1', now.read_text())

    def test_finish_accept_reported_flag(self):
        self.built('B1')
        code, out, err = self.cli('finish')
        self.assertEqual(2, code)
        self.assertIn('All tasks must be accepted: B1', err)
        code, out, err = self.cli('finish', '--accept-reported')
        self.assertEqual('accepted', self.engine.status()['tasks']['B1']['state'])


if __name__ == '__main__':
    unittest.main()
