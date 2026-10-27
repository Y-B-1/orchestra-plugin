"""live-matrix run state (F131): a reused OUT_DIR must not let a scenario find an earlier run. No Claude session runs."""
import contextlib
import hashlib
import importlib.util
import io
import os
import pathlib
import tempfile
import unittest
from unittest import mock

PATH = pathlib.Path(__file__).resolve().parent.parent / 'scripts/live-matrix.py'
spec = importlib.util.spec_from_file_location('live_matrix', PATH)
lm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lm)


class StaleRunStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        patch = mock.patch.dict(os.environ, XDG_STATE_HOME=str(self.tmp / 'state'))
        patch.start()
        self.addCleanup(patch.stop)

    def identity_dir(self, repo):
        digest = hashlib.sha256(os.path.realpath(repo).encode()).hexdigest()[:24]
        return self.tmp / 'state' / 'orchestra' / digest

    def test_a_scenario_refuses_an_earlier_run_at_the_same_path(self):
        root = self.tmp / 'out'
        lm.Ctx(root, 'g1')
        stale = self.identity_dir(root / 'g1' / 'repo')
        stale.mkdir(parents=True)
        (stale / 'state.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'earlier run'):
            lm.Ctx(root, 'g1')
        self.assertTrue((stale / 'state.json').is_file())  # the harness never removes run state

    def test_a_fresh_scenario_starts(self):
        lm.Ctx(self.tmp / 'out', 'g1')


class CrashRowTest(unittest.TestCase):
    def test_a_crashed_scenario_says_so_in_the_failed_column(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = lm.summary([{'id': 'g1', 'checks': [], 'error': 'RuntimeError: x', 'seconds': 0}])
        self.assertEqual(code, 1)
        row = next(line for line in out.getvalue().splitlines() if line.startswith('g1'))
        self.assertIn('crash', row.split()[2])


if __name__ == '__main__':
    unittest.main()
