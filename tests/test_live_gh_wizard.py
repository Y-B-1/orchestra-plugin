"""Static checks on the L2 live wizard. The wizard needs GitHub credentials and a throwaway repository, so no test runs
it: these read its text and ask bash to parse it."""
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/live-gh-wizard.sh'
RISKY = re.compile(r'\b(gh repo create|gh pr create|gh pr merge|git push|gh repo delete)\b')
FUNCTION = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*\(\)\s*\{')
SAYS = re.compile(r'^\s*(echo|printf|confirm|#)\b')


class WizardTest(unittest.TestCase):
    def lines(self):
        self.assertTrue(SCRIPT.is_file(), 'scripts/live-gh-wizard.sh is missing')
        return SCRIPT.read_text().splitlines()

    def test_bash_parses(self):
        self.lines()
        done = subprocess.run(['bash', '-n', str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_every_github_change_follows_a_confirm_in_its_function(self):
        lines = self.lines()
        risky = 0
        for number, line in enumerate(lines):
            if SAYS.match(line) or not RISKY.search(line):
                continue
            risky += 1
            start = next((i for i in range(number, -1, -1) if FUNCTION.match(lines[i])), None)
            self.assertIsNotNone(start, 'line %d is outside a function: %s' % (number + 1, line.strip()))
            self.assertTrue(any(re.match(r'\s*confirm\b', lines[i]) for i in range(start, number)),
                            'no confirm before line %d: %s' % (number + 1, line.strip()))
        self.assertGreaterEqual(risky, 4)

    def test_repo_delete_is_only_printed(self):
        lines = self.lines()
        found = [line for line in lines if 'gh repo delete' in line and not line.lstrip().startswith('#')]
        self.assertTrue(found, 'the cleanup command is never printed')
        for line in found:
            self.assertRegex(line, r'^\s*(echo|printf)\b')

    def test_state_stays_in_the_scratch_directory(self):
        text = '\n'.join(self.lines())
        self.assertRegex(text, r'export XDG_STATE_HOME=')
        self.assertIn('mktemp -d', text)

    def test_no_personal_path_or_account(self):
        text = '\n'.join(self.lines())
        self.assertNotIn('/Users/', text)
        self.assertNotIn('/home/', text)

    def test_refuses_an_existing_repository_and_this_one(self):
        text = '\n'.join(self.lines())
        self.assertIn('gh repo view', text)
        self.assertIn('remote get-url', text)
        self.assertIn('/dev/tty', text)


if __name__ == '__main__':
    unittest.main()
