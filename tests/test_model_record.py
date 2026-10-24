"""The hooks record the main session's model, and a prompt names the cards that need another model."""
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_engine as te
from orchestra_core import hooks as hooks_module
from orchestra_core.hooks import handle_event

SONNET, HAIKU = 'claude-sonnet-5-5', 'claude-haiku-5-5'


def context(reply):
    return reply.get('hookSpecificOutput', {}).get('additionalContext') or ''


class ModelCase(te.EngineFixture):
    def recorded(self):
        return self.engine.view()['session']['model']

    def transcript(self, lines):
        path = self.root / 'main.jsonl'
        path.write_text(''.join(line if isinstance(line, str) else json.dumps(line) + '\n' for line in lines))
        return str(path)

    def assistant(self, model):
        return {'type': 'assistant', 'message': {'role': 'assistant', 'model': model, 'content': []}}

    def start(self, **extra):
        payload = dict({'session_id': 's1', 'source': 'startup'}, **extra)
        return handle_event('SessionStart', payload, engine=self.engine, state_dir=str(self.engine.state_dir))

    def prompt(self, **extra):
        payload = dict({'prompt': 'next', 'session_id': 's1'}, **extra)
        return hooks_module.prompt_board(payload, self.engine)

    def run_hook(self, name, payload):
        with mock.patch.object(hooks_module, '_run_location', return_value=(self.repo, self.engine.state_dir)), \
                mock.patch('sys.stdout', new=io.StringIO()) as out:
            code = getattr(hooks_module, name)(dict({'cwd': str(self.repo)}, **payload))
        return code, out.getvalue()


class SessionStartTests(ModelCase):
    def test_the_payload_model_is_recorded(self):
        self.start(model=SONNET)
        self.assertEqual(self.recorded(), SONNET)

    def test_without_a_payload_model_the_last_assistant_entry_of_the_transcript_is_recorded(self):
        path = self.transcript([self.assistant(HAIKU), {'type': 'user', 'message': {'content': 'x'}}, self.assistant(SONNET)])
        self.start(transcript_path=path)
        self.assertEqual(self.recorded(), SONNET)

    def test_a_worker_session_records_nothing(self):
        self.start(model=SONNET, agent_type='orchestra:builder')
        self.assertIsNone(self.recorded())

    def test_a_subagent_payload_records_nothing(self):
        self.start(model=SONNET, agent_id='a1')
        self.assertIsNone(self.recorded())

    def test_a_malformed_transcript_changes_nothing_and_the_context_still_returns(self):
        path = self.transcript(['not json\n', '{"type": "assistant", "message": 5}\n', '[1]\n'])
        result = self.start(transcript_path=path)
        self.assertIsNone(self.recorded())
        self.assertIn('additionalContext', result.output['hookSpecificOutput'])

    def test_a_missing_transcript_changes_nothing(self):
        self.start(transcript_path=str(self.root / 'absent.jsonl'))
        self.assertIsNone(self.recorded())


class ModelSwitchTests(ModelCase):
    def test_the_target_model_is_recorded_and_the_answer_is_empty(self):
        code, out = self.run_hook('_model_switch', {'from_model': HAIKU, 'to_model': SONNET})
        self.assertEqual((code, json.loads(out)), (0, {}))
        self.assertEqual(self.recorded(), SONNET)

    def test_junk_changes_nothing_and_still_exits_zero(self):
        code, out = self.run_hook('_model_switch', {'to_model': 7})
        self.assertEqual((code, json.loads(out)), (0, {}))
        self.assertIsNone(self.recorded())

    def test_a_subagent_payload_records_nothing(self):
        self.run_hook('_model_switch', {'to_model': SONNET, 'agent_id': 'a1'})
        self.assertIsNone(self.recorded())

    def test_the_event_is_registered(self):
        config = json.loads((pathlib.Path(hooks_module.__file__).resolve().parents[2] / 'hooks/claude.json').read_text())
        command = config['hooks']['PostModelSwitch'][0]['hooks'][0]['command']
        self.assertTrue(command.endswith('run-hook.sh" PostModelSwitch --harness claude'), command)


class PromptTests(ModelCase):
    def test_a_mechanical_card_is_listed_in_a_sonnet_session(self):
        self.task('m', mode='mechanical')
        self.task('b')
        text = context(self.prompt(transcript_path=self.transcript([self.assistant(SONNET)])))
        self.assertIn('Session model: %s' % SONNET, text)
        self.assertIn('Cards that must go to a worker (another model): m (%s high).' % HAIKU, text)
        self.assertNotIn('b (', text)

    def test_nothing_is_listed_when_every_card_fits(self):
        self.task('b')
        text = context(self.prompt(transcript_path=self.transcript([self.assistant(SONNET)])))
        self.assertNotIn('Session model', text)

    def test_the_effort_comes_from_the_environment(self):
        self.task('m', mode='mechanical')
        with mock.patch.dict('os.environ', {'CLAUDE_EFFORT': 'high'}):
            text = context(self.prompt(transcript_path=self.transcript([self.assistant(SONNET)])))
        self.assertIn('Session model: %s high.' % SONNET, text)

    def test_more_than_eight_cards_end_with_a_count(self):
        for i in range(10):
            self.task('m%d' % i, mode='mechanical')
        text = context(self.prompt(transcript_path=self.transcript([self.assistant(SONNET)])))
        self.assertIn('m7 (', text)
        self.assertNotIn('m8 (', text)
        self.assertIn('+2.', text)

    def test_an_unknown_model_with_a_queued_builder_says_so(self):
        self.task('b')
        self.assertIn('Session model: unknown; the engine refuses no inline card on model grounds.', context(self.prompt()))

    def test_an_unknown_model_without_a_builder_card_says_nothing(self):
        self.task('c', role='critic', mode='judge', files=[])
        self.assertNotIn('Session model', context(self.prompt()))

    def test_a_malformed_transcript_changes_nothing_and_the_hook_exits_zero(self):
        self.task('m', mode='mechanical')
        path = self.transcript(['\x00garbage\n'])
        code, out = self.run_hook('_prompt_submit', {'prompt': 'next', 'session_id': 's1', 'transcript_path': path})
        self.assertEqual(code, 0)
        json.loads(out)
        self.assertIsNone(self.recorded())

    def test_the_line_repeats_only_when_it_changes(self):
        self.task('m', mode='mechanical')
        path = self.transcript([self.assistant(SONNET)])
        self.assertIn('Session model', context(self.prompt(transcript_path=path)))
        self.assertEqual(self.prompt(transcript_path=path), {})


if __name__ == '__main__':
    unittest.main()


class FirstTurnRecordTests(ModelCase):
    """Live m1: a new session has no assistant line at SessionStart or at its first prompt, and a headless SessionStart
    carries no model; the model is recorded at the first orchestra.py Bash call and at Stop, from the transcript."""

    def bash(self, command, **extra):
        payload = dict({'session_id': 's1', 'tool_name': 'Bash', 'tool_input': {'command': command}}, **extra)
        return handle_event('PreToolUse', payload, engine=self.engine, state_dir=str(self.engine.state_dir), mode='minimal')

    def test_an_orchestra_bash_call_records_the_model_from_the_transcript(self):
        path = self.transcript([self.assistant(SONNET)])
        self.bash('python3 /x/scripts/orchestra.py --lease L inline M1', transcript_path=path)
        self.assertEqual(SONNET, self.recorded())

    def test_another_bash_call_records_nothing(self):
        path = self.transcript([self.assistant(SONNET)])
        self.bash('git status', transcript_path=path)
        self.assertIsNone(self.recorded())

    def test_a_worker_call_records_nothing(self):
        path = self.transcript([self.assistant(HAIKU)])
        self.bash('python3 /x/scripts/orchestra.py status', transcript_path=path, agent_id='a1')
        self.assertIsNone(self.recorded())

    def test_stop_records_the_model(self):
        path = self.transcript([self.assistant(SONNET)])
        handle_event('Stop', {'session_id': 's1', 'transcript_path': path}, engine=self.engine, state_dir=str(self.engine.state_dir))
        self.assertEqual(SONNET, self.recorded())

    def test_an_unchanged_model_does_not_rewrite_the_state(self):
        path = self.transcript([self.assistant(SONNET)])
        self.bash('python3 /x/scripts/orchestra.py status', transcript_path=path)
        before = self.engine.state_path.stat().st_mtime_ns
        self.bash('python3 /x/scripts/orchestra.py status', transcript_path=path)
        self.assertEqual(before, self.engine.state_path.stat().st_mtime_ns)
