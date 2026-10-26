"""2.15.1 docs checks: the README command table, one statement of each coordinator rule, and docs that match the code."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins' / 'orchestra' / 'scripts'))

import orchestra  # noqa: E402
from orchestra_core import hooks  # noqa: E402

SKILL_DIR = ROOT / 'plugins' / 'orchestra' / 'skills' / 'orchestra'
LOADED = ('SKILL.md', 'references/coordination.md', 'references/parallel.md', 'references/triage.md', 'references/cli.md')


def text(rel):
    return (ROOT / rel).read_text()


def loaded(name):
    return (SKILL_DIR / name).read_text()


class ReadmeCommandTableTests(unittest.TestCase):
    def table_words(self):
        rows = [line for line in text('README.md').splitlines() if line.startswith('|')]
        return {span.split()[0] for row in rows for span in re.findall(r'`([^`]+)`', row) if span.split()}

    def test_every_top_level_subcommand_is_in_the_readme_table(self):
        sub = next(a for a in orchestra.parser()._actions if getattr(a, 'choices', None))
        missing = sorted(set(sub.choices) - self.table_words())
        self.assertEqual([], missing)


class OneStatementTests(unittest.TestCase):
    def test_model_fit_rule_is_stated_in_one_loaded_file(self):
        rule = re.compile(r'higher effort|model family|own model and effort|your model and effort|session.s model', re.I)
        self.assertEqual(['SKILL.md'], [name for name in LOADED if rule.search(loaded(name))])

    def test_no_fold_sentence_in_the_loaded_set(self):
        for name in LOADED:
            self.assertNotIn('Fold one role', loaded(name), name)

    def test_live_matrix_cites_no_unlinked_article(self):
        self.assertNotIn('folding subagents', text('docs/live-matrix.md'))

    def test_wave_does_not_claim_wave_now(self):
        for line in loaded('references/cli.md').splitlines():
            if 'wave_now' in line:
                self.assertTrue(line.startswith('`waves` '), line)


class WordingMatchesCodeTests(unittest.TestCase):
    def test_hooks_doc_quotes_the_decide_or_park_clause(self):
        clause = hooks.DECIDE_OR_PARK.split('. ')[1] + '.'
        self.assertIn(clause, text('docs/hooks.md'))
        self.assertNotIn('decide it yourself, record the decision', text('docs/hooks.md'))

    def test_hooks_doc_names_every_model_recording_point(self):
        doc = text('docs/hooks.md')
        self.assertNotIn('three hook points', doc)
        self.assertIn('five hook events', doc)
        for point in ('SessionStart', 'PostModelSwitch', 'UserPromptSubmit', 'Stop', 'PreToolUse'):
            self.assertIn(point, doc.split('## Model fit')[1].split('##')[0])

    def test_escalation_is_the_third_unchanged_pass(self):
        for rel in ('docs/cli.md', 'CHANGELOG.md', 'docs/release-notes/v2.15.0.md'):
            self.assertNotIn('three unchanged nudges', text(rel), rel)
            self.assertIn('third unchanged pass', text(rel), rel)

    def test_changelog_corrects_the_2150_wording(self):
        section = text('CHANGELOG.md').split('## 2.15.1')[1].split('\n## ')[0]
        for word in ('DECIDE_OR_PARK', 'unpark', 'five hook events', '`timeoutMs`'):
            self.assertIn(word, section)

    def test_2151_release_notes_exist(self):
        self.assertTrue((ROOT / 'docs/release-notes/v2.15.1.md').is_file())


class SharedCodeTests(unittest.TestCase):
    def test_efforts_has_one_definition(self):
        from orchestra_core import engine
        self.assertIs(engine.EFFORTS, hooks.EFFORTS)
        self.assertEqual(1, len(re.findall(r'^EFFORTS = ', text('plugins/orchestra/scripts/orchestra_core/hooks.py')
                                           + text('plugins/orchestra/scripts/orchestra_core/engine.py')
                                           + text('plugins/orchestra/scripts/orchestra_core/models.py'), re.M)))

    def test_hooks_share_a_transcript_tail_reader_and_an_rm_operand_reader(self):
        self.assertTrue(callable(hooks._transcript_tail))
        self.assertTrue(callable(hooks._rm_operands))
        self.assertEqual(1, text('plugins/orchestra/scripts/orchestra_core/hooks.py').count('256 * 1024') + text(
            'plugins/orchestra/scripts/orchestra_core/hooks.py').count('262144'))

    def test_brief_builder_tests_only_the_reasons_a_stop_can_carry(self):
        source = text('plugins/orchestra/scripts/orchestra_core/engine.py')
        self.assertNotIn("reason in ('stalled'", source)
        self.assertNotIn("reason in ('gate-failing'", source)


class WorkerReportAcceptTests(unittest.TestCase):
    def test_cli_guide_documents_do_report_and_accept(self):
        self.assertIn('do "report W T F" "accept ID"', text('docs/cli.md'))


if __name__ == '__main__':
    unittest.main()
