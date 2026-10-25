"""`status --brief`: a compact, lease-free summary that stays small however many cards the run holds."""
import contextlib
import io
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))

import orchestra
import test_acceptance as ta

PLUGIN = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/.claude-plugin/plugin.json').read_text())


class StatusBriefTests(ta.CliFixture):
    def brief(self):
        raw = ['--repo', str(self.repo), '--state', str(self.engine.state_dir), 'status', '--brief']
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = orchestra.main(raw)
        self.assertEqual(0, code)
        return out.getvalue(), json.loads(out.getvalue())

    def many(self, running, reported):
        state = json.loads(self.engine.state_path.read_text())
        for i in range(running + reported):
            name = 'card-%03d' % i
            state['tasks'][name] = dict(id=name, role='builder', mode='implementation', state='running' if i < running else 'reported',
                                        worker='orchestra-' + name, inline=i % 7 == 0, started_at=self.engine._clock() - 90 - i,
                                        inputs=['x'], acceptance=['y' * 200], files=['f%d' % i], resources=[], dependencies=[])
        self.engine.state_path.write_text(json.dumps(state))

    def test_shape_and_keys(self):
        self.running('a')
        text, brief = self.brief()
        self.assertEqual({'counts', 'running', 'reported', 'lease', 'autonomy', 'versions'}, set(brief))
        self.assertEqual(1, brief['counts']['running'])
        entry = brief['running'][0]
        self.assertEqual({'id', 'role', 'mode', 'worker', 'inline', 'age_s'}, set(entry))
        self.assertEqual(('a', 'builder', 'w-a', False), (entry['id'], entry['role'], entry['worker'], entry['inline']))
        self.assertGreaterEqual(entry['age_s'], 0)
        self.assertEqual({'holder', 'active', 'outcome'}, set(brief['lease']))
        self.assertTrue(brief['lease']['active'])
        self.assertEqual({'active', 'passes', 'deadline', 'last_stop_reason'}, set(brief['autonomy']))
        self.assertEqual(PLUGIN['version'], brief['versions']['engine'])
        self.assertEqual(1, brief['versions']['state'])
        self.assertEqual(PLUGIN['version'], brief['versions']['written_by'])
        self.assertNotIn('note', brief['versions'])

    def test_a_large_run_stays_under_4096_bytes_with_capped_lists(self):
        self.many(60, 90)
        text, brief = self.brief()
        self.assertLess(len(text.encode()), 4096)
        self.assertEqual(60, brief['counts']['running'])
        self.assertEqual(90, brief['counts']['reported'])
        self.assertEqual(21, len(brief['running']))
        self.assertEqual('+40', brief['running'][-1])
        self.assertEqual(41, len(brief['reported']))
        self.assertEqual('+50', brief['reported'][-1])

    def test_an_older_engine_version_in_state_adds_a_note(self):
        state = json.loads(self.engine.state_path.read_text())
        state['engine_version'] = '0.0.1'
        self.engine.state_path.write_text(json.dumps(state))
        _, brief = self.brief()
        self.assertEqual('0.0.1', brief['versions']['written_by'])
        self.assertEqual('state last written by engine 0.0.1; this is engine ' + PLUGIN['version'], brief['versions']['note'])

    def test_plain_status_still_prints_the_full_state(self):
        self.running('a')
        code, out, _ = self.cli('status', lease=False)
        self.assertEqual(0, code)
        self.assertIn('tasks', out)
        self.assertEqual(PLUGIN['version'], out['engine_version'])


if __name__ == '__main__':
    unittest.main()
