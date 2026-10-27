import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
from orchestra_core import guards

SUITES = [
    'python3 -m coverage run -m pytest', 'python3 -m coverage run -m unittest discover',
    'python3 -m coverage run --branch -m pytest -q', 'coverage run -m pytest',
    'python3 -Im unittest', 'python3 -Bm pytest', 'python3 -IBm pytest', 'python3 -Bmpytest', 'python3 -Impytest',
    'python3 -m unittest a.b.c', 'python3 -B -m pytest', 'python3 -W error -m pytest', 'python3 -munittest',
]
NOT_SUITES = [
    'python3 script.py -m unittest', 'python3 script.py -munittest', 'python3 script.py -Bm pytest',
    'python3 -B script.py -m pytest', 'python3 -m coverage run script.py -m pytest',
    'python3 -m coverage run -m pytest tests/a.py::test_x', 'python3 -m coverage report',
    'python3 -c "print(1)" -m pytest',
]


class SuiteProbe2153(unittest.TestCase):
    def test_suites_read_as_suites(self):
        for command in SUITES:
            with self.subTest(command=command):
                self.assertTrue(guards.runs_test_suite(command))

    def test_script_arguments_and_probes_are_not_suites(self):
        for command in NOT_SUITES:
            with self.subTest(command=command):
                self.assertFalse(guards.runs_test_suite(command))


if __name__ == '__main__':
    unittest.main()
