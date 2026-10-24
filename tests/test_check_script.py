"""F57b: scripts/check.sh runs the mod tests before the background unit suites; live-matrix.py removes only its own
scenario directories and its d4 status check matches only an orchestra.py status command."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = (ROOT / 'scripts' / 'check.sh').read_text()


def _matrix():
    spec = importlib.util.spec_from_file_location('live_matrix', ROOT / 'scripts' / 'live-matrix.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CheckOrderTests(unittest.TestCase):
    def test_mod_tests_run_before_the_background_unit_suites(self):
        mod = CHECK.index('run mod-tests')
        background = CHECK.index('-m unittest discover -s tests >')
        self.assertLess(mod, background, 'mod-tests must finish before the unit suites load the machine')

    def test_quick_still_skips_the_unit_suites(self):
        self.assertIn('SKIPPED  unit suite (--quick)', CHECK)
        self.assertIn('if [ $quick -eq 0 ]; then', CHECK)


class LiveMatrixSafetyTests(unittest.TestCase):
    def test_an_unmarked_scenario_directory_is_not_removed(self):
        m = _matrix()
        with tempfile.TemporaryDirectory() as root:
            keep = Path(root) / 'g0'
            keep.mkdir()
            (keep / 'mine.txt').write_text('not the harness')
            with self.assertRaises(SystemExit) as caught:
                m.clear_scenario_dir(keep)
            self.assertIn(str(keep), str(caught.exception))
            self.assertTrue((keep / 'mine.txt').exists())

    def test_a_marked_scenario_directory_is_replaced(self):
        m = _matrix()
        with tempfile.TemporaryDirectory() as root:
            old = Path(root) / 'g0'
            old.mkdir()
            (old / m.MARKER).write_text('')
            (old / 'stale.txt').write_text('old run')
            m.clear_scenario_dir(old)
            self.assertFalse((old / 'stale.txt').exists())
            self.assertTrue((old / m.MARKER).exists())

    def test_a_missing_scenario_directory_is_created_with_the_marker(self):
        m = _matrix()
        with tempfile.TemporaryDirectory() as root:
            new = Path(root) / 'g0'
            m.clear_scenario_dir(new)
            self.assertTrue((new / m.MARKER).exists())

    def test_d4_status_match_needs_an_orchestra_status_command(self):
        m = _matrix()
        self.assertFalse(m.is_orchestra_status('git status --short'))
        self.assertFalse(m.is_orchestra_status('python3 /x/orchestra.py --lease abc status'))
        self.assertTrue(m.is_orchestra_status('python3 /x/scripts/orchestra.py status'))


if __name__ == '__main__':
    unittest.main()
