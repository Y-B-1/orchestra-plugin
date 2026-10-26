"""2.15.2 pre-PR review: the F105 acceptance check also reads text outside code spans (repair of RVC's blocking finding),
`resume` restarts the silence clock, `replace` waits for a running review of the old card, and a ruling names a check
only by whole words."""
import pathlib
import sys
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine_2152 as t2
from orchestra_core.engine import EngineError
from test_refusal_texts import RefusalFixture


class MixedAcceptanceLineTests(RefusalFixture):
    def setUp(self):
        super().setUp()
        (self.repo / 'tests').mkdir()
        (self.repo / 'tests' / 'test_packaging.py').write_text('')

    def test_a_typo_outside_the_code_spans_is_refused(self):
        line = "python3 -m unittest discover -s tests -p 'test_pakaging.py' exits 0 (see `docs/cli.md`)."
        self.assertIn('Acceptance matches no test file', self.refusal(self.task, 'a', acceptance=[line]))

    def test_a_correct_command_outside_the_spans_is_accepted(self):
        self.task('b', acceptance=["python3 -m unittest discover -s tests -p 'test_packaging.py' exits 0 (see `docs/cli.md`)."])


class ResumeClockTests(t2.Fixture):
    def test_resume_restarts_the_silence_clock(self):
        self.reported('a')
        data = self.raw()
        data['tasks']['a']['started_at'] = time.time() - 10_000
        self.engine.state_path.write_text(t2.json.dumps(data))
        before = time.time()
        self.engine.resume_card('main', self.lease, 'a')
        self.assertGreaterEqual(self.cards()['a']['started_at'], before)


class ReplaceUnderReviewTests(t2.Fixture):
    def test_replace_waits_for_a_running_review_of_the_old_card(self):
        self.reported('OLD')
        self.task('REV', role='code-reviewer', mode='final', review_of=['OLD'], files=[])
        self.engine.dispatch('main', self.lease, 'REV', 'w-REV')
        with self.assertRaisesRegex(EngineError, 'review'):
            self.replace('OLD', t2.card('NEW'))
        self.assertIn('OLD', self.cards())
        self.assertEqual(['OLD'], self.cards()['REV']['review_of'])


class RulingWordTests(t2.Fixture):
    def failing(self, command):
        self.reported('a', checks=[{'command': command, 'exit_code': 1}])

    def test_a_ruling_names_a_check_only_by_whole_words(self):
        cases = [('python3 -m unittest tests.test_a', 'tests.test_ab is flaky'),
                 ('cd plugins/orchestra && npm test', 'the npm lint in plugins/orchestra is noisy'),
                 ('scripts/check.sh', 'scripts/check.sh --quick passed; full check skipped')]
        for n, (command, ruling) in enumerate(cases):
            with self.subTest(command=command):
                self.setUp()
                self.failing(command)
                with self.assertRaisesRegex(EngineError, 'failing check'):
                    self.engine.accept('main', self.lease, 'a', ruling=ruling)

    def test_the_whole_command_or_its_test_target_still_names_it(self):
        for command, ruling in [('python3 -m unittest tests.test_a', 'tests.test_a is a known flake'),
                                ('scripts/check.sh', 'scripts/check.sh fails on the clock only')]:
            with self.subTest(command=command):
                self.setUp()
                self.failing(command)
                self.engine.accept('main', self.lease, 'a', ruling=ruling)


class ModelLineScopeTests(t2.Fixture):
    """RVC out-of-scope note: the prompt Model fit line names only cards the engine would refuse inline on model
    grounds; a review card always runs on a worker and a tiny card folds whatever the model."""
    def setUp(self):
        super().setUp()
        from orchestra_core.engine import Engine
        self.engine = Engine(self.root / 'sized', self.repo)
        self.lease = self.engine.open_session('main', size='medium', asks=2)

    def test_review_and_tiny_cards_are_not_listed(self):
        from orchestra_core import hooks
        self.engine.record_model('claude-haiku-5-5', 'high')
        self.task('B1')
        self.task('T1', size='tiny')
        self.task('R1', role='code-reviewer', mode='final', review_of=['B1'], files=[])
        line = hooks._model_line(self.engine, self.engine.view()) or ''
        self.assertIn('B1', line)
        self.assertNotIn('T1', line)
        self.assertNotIn('R1', line)


if __name__ == '__main__':
    unittest.main()
