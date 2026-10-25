"""Autonomy answers its own questions: the AskUserQuestion hook, the armed Stop question rule and the nested descriptor copy."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(HERE))

from orchestra_core.hooks import handle_event
from test_live_fixes import LiveFixture

CONTINUE = 'Continue one authorized bounded pass'
PARK = "park the card with `orchestra.py park TASK --reason 'needs-owner: <the question>'`"


def question(text, labels, multi=False):
    return {'question': text, 'header': 'h', 'multiSelect': multi,
            'options': [{'label': label, 'description': 'd'} for label in labels]}


class AskFixture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.state = pathlib.Path(self.dir.name)

    def engine(self, armed=True):
        engine = mock.Mock()
        engine.autonomy_active.return_value = armed
        engine.state_dir = self.state
        engine.hook_stop.return_value = CONTINUE
        return engine

    def ask(self, questions, engine='default', **extra):
        engine = self.engine() if engine == 'default' else engine
        payload = {'tool_name': 'AskUserQuestion', 'tool_input': {'questions': questions}, **extra}
        return handle_event('PreToolUse', payload, engine=engine).output

    def progress(self):
        path = self.state / 'progress.md'
        return path.read_text() if path.exists() else ''


class AskUserQuestionTest(AskFixture):
    def test_every_question_with_a_recommended_option_is_answered_and_logged(self):
        questions = [question('Which db?', ['Mongo', 'Postgres (Recommended)']),
                     question('Which tests?', ['all', 'few  (recommended)  '])]
        out = self.ask(questions)['hookSpecificOutput']
        self.assertEqual(out['permissionDecision'], 'allow')
        self.assertEqual(out['updatedInput']['questions'], questions)
        self.assertEqual(out['updatedInput']['answers'], {'Which db?': 'Postgres (Recommended)',
                                                           'Which tests?': 'few  (recommended)  '})
        lines = self.progress().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('- decided for the owner: Which db? -> Postgres (Recommended) (at 20'), lines[0])
        self.assertTrue(lines[1].startswith('- decided for the owner: Which tests? -> '), lines[1])

    def test_a_multi_select_joins_every_recommended_label(self):
        questions = [question('Which?', ['a (Recommended)', 'b', 'c (Recommended)'], multi=True)]
        out = self.ask(questions)['hookSpecificOutput']
        self.assertEqual(out['updatedInput']['answers'], {'Which?': 'a (Recommended), c (Recommended)'})

    def test_a_question_without_a_recommended_option_is_denied_and_nothing_is_logged(self):
        out = self.ask([question('A?', ['x (Recommended)']), question('B?', ['y', 'z'])])['hookSpecificOutput']
        self.assertEqual(out['permissionDecision'], 'deny')
        self.assertIn('Autonomy is armed and the owner is away. Decide this yourself', out['permissionDecisionReason'])
        self.assertIn(PARK, out['permissionDecisionReason'])
        self.assertEqual(self.progress(), '')

    def test_a_question_from_another_session_or_a_worker_gets_no_decision(self):
        engine = self.engine()
        engine.status.return_value = {'session': {'harness_session': 'H1'}}
        questions = [question('Which db?', ['Mongo', 'Postgres (Recommended)'])]
        self.assertEqual(self.ask(questions, engine=engine, session_id='H2'), {})
        self.assertEqual(self.ask(questions, engine=engine, session_id='H1', agent_id='a1'), {})
        self.assertEqual(self.progress(), '')
        out = self.ask(questions, engine=engine, session_id='H1')['hookSpecificOutput']
        self.assertEqual(out['permissionDecision'], 'allow')

    def test_malformed_questions_are_denied(self):
        for questions in ([], 'text', None, [{'question': 'q'}], ['q'], [{'question': 'q', 'options': 'x'}],
                          [{'question': 'q', 'options': ['x (Recommended)']}], [{'options': [{'label': 'x (Recommended)'}]}]):
            with self.subTest(questions=questions):
                out = self.ask(questions)['hookSpecificOutput']
                self.assertEqual(out['permissionDecision'], 'deny')
                self.assertIn('Decide this yourself', out['permissionDecisionReason'])

    def test_unarmed_or_without_an_engine_there_is_no_decision(self):
        questions = [question('Which?', ['a (Recommended)'])]
        self.assertEqual(self.ask(questions, engine=self.engine(armed=False)), {})
        self.assertEqual(self.ask(questions, engine=None), {})
        self.assertEqual(self.ask([question('Which?', ['a'])], engine=None), {})
        self.assertEqual(self.progress(), '')


class StopQuestionTest(AskFixture):
    def stop(self, engine='default', **payload):
        engine = self.engine() if engine == 'default' else engine
        return handle_event('Stop', payload, engine=engine).output

    def test_a_question_in_the_last_message_appends_the_decide_or_park_text(self):
        out = self.stop(last_assistant_message='Done with the card. Shall I continue with the next one?')
        self.assertEqual(out['decision'], 'block')
        self.assertTrue(out['reason'].startswith(CONTINUE), out['reason'])
        self.assertIn('Decide this yourself', out['reason'])
        self.assertIn(PARK, out['reason'])

    def test_a_message_without_a_question_leaves_the_reason_unchanged(self):
        self.assertEqual(self.stop(last_assistant_message='All done.'), {'decision': 'block', 'reason': CONTINUE})
        self.assertEqual(self.stop(), {'decision': 'block', 'reason': CONTINUE})

    def test_only_the_last_600_characters_count(self):
        message = 'Why? ' + 'x' * 700
        self.assertEqual(self.stop(last_assistant_message=message), {'decision': 'block', 'reason': CONTINUE})

    def test_the_transcript_is_the_fallback_for_the_last_assistant_text(self):
        path = self.state / 't.jsonl'
        rows = [{'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Which one?'}]}},
                {'type': 'user', 'message': {'role': 'user', 'content': 'go'}},
                {'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'tool_use', 'name': 'Bash'}]}},
                {'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Ready to go on?'}]}}]
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
        out = self.stop(transcript_path=str(path))
        self.assertIn('Decide this yourself', out['reason'])
        rows[-1]['message']['content'][0]['text'] = 'Finished.'
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
        self.assertEqual(self.stop(transcript_path=str(path)), {'decision': 'block', 'reason': CONTINUE})

    def test_an_unreadable_transcript_means_no_question(self):
        self.assertEqual(self.stop(transcript_path=str(self.state / 'missing.jsonl')), {'decision': 'block', 'reason': CONTINUE})
        (self.state / 'bad.jsonl').write_text('not json\n{"type": "assistant"}\n')
        self.assertEqual(self.stop(transcript_path=str(self.state / 'bad.jsonl')), {'decision': 'block', 'reason': CONTINUE})

    def test_unarmed_the_stop_is_unchanged(self):
        engine = self.engine(armed=False)
        engine.hook_stop.return_value = None
        engine.view.side_effect = RuntimeError('no board')
        self.assertEqual(self.stop(engine=engine, last_assistant_message='Shall I?'), {})


class MatcherTest(unittest.TestCase):
    def test_the_matchers_include_ask_user_question_and_agree(self):
        rules = json.loads((ROOT / 'plugins/orchestra/config/guard-rules.json').read_text())
        hooks = json.loads((ROOT / 'plugins/orchestra/hooks/claude.json').read_text())
        matcher = hooks['hooks']['PreToolUse'][0]['matcher']
        self.assertIn('AskUserQuestion', rules['tools']['claude_matcher'].split('|'))
        self.assertEqual(rules['tools']['claude_matcher'], matcher)


class NestedDescriptorCopyTest(LiveFixture):
    def test_a_descriptor_copy_in_a_quoted_nested_shell_is_allowed_after_a_cd_into_the_state(self):
        s = str(self.state)
        for command in ('cd %s && sh -c "echo x >&2"' % s, "cd %s && sh -c 'echo x 2>&1'" % s):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command, session_id='s1'), 'allow')

    def test_a_file_name_starting_with_a_digit_stays_denied(self):
        s = str(self.state)
        for command in ('cd %s && echo x >&1new.json' % s, 'cd %s && sh -c "echo x >&1new.json"' % s,
                        'cd %s && sh -c \'echo x >&1"new.json"\'' % s):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command, session_id='s1'), 'deny')

    def test_a_descriptor_copy_followed_by_an_empty_quote_pair_and_a_path_stays_a_write(self):
        s = str(self.state)
        (self.state / '1').mkdir()
        for command in ('cd %s && echo x >&1""/../state.json' % s, "cd %s && echo x >&1''/../state.json" % s):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command, session_id='s1'), 'deny')


if __name__ == '__main__':
    unittest.main()
