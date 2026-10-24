"""live-matrix --repeat: aggregation of repeated scenario runs and the run directory names. No Claude session runs."""
import contextlib
import importlib.util
import io
import pathlib
import tempfile
import unittest
from unittest import mock

PATH = pathlib.Path(__file__).resolve().parent.parent / 'scripts/live-matrix.py'
spec = importlib.util.spec_from_file_location('live_matrix', PATH)
lm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lm)


def result(sid='g1', ok=True, error=None):
    return {'id': sid, 'seconds': 3, 'error': error,
            'checks': [{'check': 'first', 'pass': True, 'detail': ''}, {'check': 'second', 'pass': ok, 'detail': 'd'}]}


def summarize(results):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = lm.summary(results)
    return code, out.getvalue()


class Aggregate(unittest.TestCase):
    def test_all_runs_pass_is_pass_without_flip(self):
        code, text = summarize([lm.merge_runs([result(), result()])])
        self.assertEqual(code, 0)
        self.assertIn('RESULT: PASS', text)
        self.assertNotIn('FLIP', text)

    def test_disagreeing_runs_fail_and_name_the_flip_with_failing_checks(self):
        code, text = summarize([lm.merge_runs([result(), result(ok=False)])])
        self.assertEqual(code, 1)
        self.assertIn('RESULT: FAIL', text)
        self.assertIn('FLIP g1', text)
        self.assertIn('second', text)

    def test_all_runs_failing_is_fail_but_not_a_flip(self):
        code, text = summarize([lm.merge_runs([result(ok=False), result(ok=False)])])
        self.assertEqual(code, 1)
        self.assertIn('RESULT: FAIL', text)
        self.assertNotIn('FLIP', text)

    def test_a_crash_in_one_run_is_a_flip(self):
        merged = lm.merge_runs([result(), {'id': 'g1', 'seconds': 1, 'error': 'boom', 'checks': []}])
        code, text = summarize([merged])
        self.assertEqual(code, 1)
        self.assertIn('FLIP g1', text)
        self.assertIn('boom', text)

    def test_single_run_is_returned_unchanged(self):
        one = result(ok=False)
        self.assertIs(lm.merge_runs([one]), one)


class Layout(unittest.TestCase):
    def names(self, *argv):
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            plug = pathlib.Path(tmp) / 'plug'
            (plug / 'scripts').mkdir(parents=True)
            (plug / 'scripts/orchestra.py').write_text('')

            def fake(root, sid, name=None):
                seen.append(name or sid)
                return result(sid)
            with mock.patch.object(lm, 'run', fake), contextlib.redirect_stdout(io.StringIO()):
                code = lm.main(['--plugin', str(plug), *argv])
        return code, sorted(seen)

    def test_default_keeps_root_scenario_directory(self):
        self.assertEqual(self.names('OUT', 'g1', 'g0'), (0, ['g0', 'g1']))
        self.assertEqual(self.names('--repeat', '1', 'OUT', 'g1'), (0, ['g1']))

    def test_repeat_uses_one_directory_per_run(self):
        self.assertEqual(self.names('--repeat', '2', 'OUT', 'g1'), (0, ['g1.r1', 'g1.r2']))

    def test_repeat_below_one_is_refused(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.names('--repeat', '0', 'OUT', 'g1')


if __name__ == '__main__':
    unittest.main()
