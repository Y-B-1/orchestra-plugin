"""live-matrix d4 matcher: a lease-free `orchestra.py status` in any shell segment. No Claude session runs."""
import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parent.parent / 'scripts/live-matrix.py'
spec = importlib.util.spec_from_file_location('live_matrix', PATH)
lm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lm)

S = 'python3 /p/scripts/orchestra.py'
LEASE = '--' + 'lease'


class StatusMatch(unittest.TestCase):
    def test_matches(self):
        for cmd in [f'{S} status', f'{S} status; echo done', f'{S} status && echo ok', f'{S} status | head -3',
                    f'cd /r\n{S} status', f'false || {S} status']:
            with self.subTest(cmd=cmd):
                self.assertTrue(lm.is_orchestra_status(cmd))

    def test_rejects(self):
        for cmd in ['git status', f'{S} {LEASE} L status', f'{S} statusx', f'{S} status {LEASE} L; echo hi',
                    f'git status; echo {S}']:
            with self.subTest(cmd=cmd):
                self.assertFalse(lm.is_orchestra_status(cmd))


if __name__ == '__main__':
    unittest.main()
