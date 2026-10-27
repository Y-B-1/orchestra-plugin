"""2.15.3 docs: mods run by default from Claude Code 2.1.287, and the README states the live-check evidence."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
VAR = 'CLAUDE_CODE_ENABLE_' + 'FUNCTION_HOOKS'
# History, not current guidance: release notes, the ledger, research, and the dated plans and specs of earlier versions.
HISTORY = ('docs/release-notes/', 'docs/BUILD-LEDGER.md', 'docs/RESEARCH', 'docs/PLAN-', 'docs/SPEC-', 'docs/RELEASE-NOTES-')


class ModDocsTest(unittest.TestCase):
    def test_no_current_doc_names_the_retired_variable(self):
        files = [ROOT / 'README.md'] + sorted((ROOT / 'docs').rglob('*.md'))
        bad = []
        for f in files:
            rel = f.relative_to(ROOT).as_posix()
            if rel.startswith(HISTORY):
                continue
            if VAR in f.read_text():
                bad.append(rel)
        self.assertEqual(bad, [])

    def test_docs_say_mods_run_by_default_and_name_the_off_switches(self):
        for rel in ('README.md', 'docs/hooks.md'):
            t = (ROOT / rel).read_text()
            with self.subTest(rel=rel):
                self.assertIn('2.1.287', t)
                self.assertIn('by default', t)
                for off in ('--bare', '--safe-mode', 'disableAllHooks'):
                    self.assertIn(off, t)

    def test_readme_live_check_wording_matches_the_evidence(self):
        t = (ROOT / 'README.md').read_text()
        self.assertIn('runs real headless sessions on macOS before each release', t)
        self.assertIn('Linux and Windows are covered by unit tests only', t)
        self.assertNotIn('No platform has been checked with a live Claude Code session except Linux and macOS', t)


if __name__ == '__main__':
    unittest.main()
