"""Orchestra 2.15.1 add-time and dispatch checks: final review brief lines (F88), acceptance that matches no test file
(F94), generated outputs a source owns (F71) and the base recorded at dispatch (F80)."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core import briefs
from orchestra_core.engine import EngineError
from test_refusal_texts import RefusalFixture, report_for

FIXTURES = 'plugins/orchestra/hooks/mod/fixtures/guard-fixtures.ts'


class FinalBriefTests(RefusalFixture):
    def final(self, name, lines, **kw):
        brief = self.repo / (name + '.md')
        brief.write_text('\n'.join(['# Card', 'Mode: final', *lines]) + '\n')
        self.task(name, role='code-reviewer', mode='final', files=[], review_of=['B1'], brief=str(brief), **kw)

    def setUp(self):
        super().setUp()
        self.task('B1')

    def test_a_final_brief_without_lens_is_refused(self):
        self.assertIn('Lens:', self.refusal(self.final, 'R1', []))

    def test_a_combined_brief_needs_required_categories(self):
        self.assertIn('Required categories:', self.refusal(self.final, 'R1', ['Lens: combined']))
        self.final('R2', ['Lens: combined', 'Required categories: requirements, correctness, tests, architecture'])
        self.final('R3', ['Lens: standards'])

    def test_a_fix_re_review_needs_neither_line(self):
        state = json.loads(self.engine.state_path.read_text())
        state['tasks']['B1']['mode'] = 'repair'
        self.engine.state_path.write_text(json.dumps(state))
        self.final('R1', [])

    def test_the_skeleton_brief_carries_both_lines(self):
        self.task('R1', role='code-reviewer', mode='final', files=[], review_of=['B1'], variant='medium')
        text = briefs.card(self.engine, 'R1')
        self.assertRegex(text, r'(?m)^Lens: combined$')
        self.assertRegex(text, r'(?m)^Required categories: requirements, correctness, tests, architecture$')


class AcceptanceMatchTests(RefusalFixture):
    def setUp(self):
        super().setUp()
        (self.repo / 'tests').mkdir()
        (self.repo / 'tests' / 'test_real.py').write_text('')

    def test_a_pattern_or_dir_that_matches_no_test_file_is_refused(self):
        lines = ('python3 -m unittest discover -s tests -p "no_such_*.py"', 'python3 -B -m unittest discover -s nodir; echo $?',
                 'python3 -m unittest discover -p "test_gone.py"')
        for n, line in enumerate(lines):
            with self.subTest(line=line):
                self.assertIn('Acceptance matches no test file', self.refusal(self.task, 'a%d' % n, acceptance=[line]))

    def test_a_match_or_a_file_the_card_owns_is_accepted(self):
        self.task('a', acceptance=['python3 -m unittest discover -s tests -p "test_real.py"'])
        self.task('b', acceptance=['python3 -m unittest discover -s tests'])
        self.task('c', acceptance=['python3 -m unittest discover -s tests -p "test_new.py"'], files=['tests/test_new.py'])
        self.task('d', acceptance=['python3 -m unittest tests.test_real'])


class GeneratedOutputTests(RefusalFixture):
    def test_a_guard_source_brings_its_generated_fixture(self):
        for source in ('guard-rules.json', 'guard-corpus.json'):
            with self.subTest(source=source):
                self.task(source, files=['plugins/orchestra/config/' + source])
                self.assertEqual(['plugins/orchestra/config/' + source, FIXTURES], self.card(source)['files'])

    def test_the_output_is_not_added_twice(self):
        self.task('a', files=['plugins/orchestra/config/guard-rules.json', FIXTURES])
        self.assertEqual(2, len(self.card()['files']))


class DispatchBaseTests(RefusalFixture):
    def test_dispatch_records_a_base_so_a_stray_file_is_flagged(self):
        token = self.running('a', files=['a'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.card()['base'])
        self.engine.report('w-a', token, report_for(self.commit(a='new', stray='x')))
        self.assertIn('files outside the card: stray', self.refusal(self.engine.accept, 'main', self.lease, 'a'))


if __name__ == '__main__':
    unittest.main()
