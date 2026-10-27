"""SubagentStop capture: an Orchestra worker's final message is saved to disk and recorded as the card's report."""
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
from orchestra_core.engine import EngineError
from orchestra_core.hooks import handle_event

PLUGIN = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra'
GOOD = 'STATUS: PASS\nARTIFACT: abc123 clean\nJudged the card.'


def user_line(text):
    return json.dumps({'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'text', 'text': text}]}})


class CaptureCase(te.EngineFixture):
    def setUp(self):
        super().setUp()
        self.task('c', role='critic', mode='judge', files=[])
        self.token = self.engine.dispatch('main', self.lease, 'c', 'w1')
        self.transcript = self.root / 'agent.jsonl'
        self.write_transcript('Assignment: w1 %s\nDo the card.' % self.token)
        self.reports = self.engine.state_dir / 'reports'

    def write_transcript(self, text, content_as_string=False):
        first = json.dumps({'type': 'user', 'message': {'role': 'user', 'content': text}}) if content_as_string else user_line(text)
        self.transcript.write_text(first + '\n' + json.dumps({'type': 'assistant', 'message': {'content': 'x'}}) + '\n')

    def stop(self, message=GOOD, agent_type='orchestra:critic', active=False, engine='default', agent_id='a1', **extra):
        payload = {'agent_id': agent_id, 'agent_type': agent_type, 'agent_transcript_path': str(self.transcript),
                   'last_assistant_message': message, 'stop_hook_active': active}
        payload.update(extra)
        engine = self.engine if engine == 'default' else engine
        return handle_event('SubagentStop', payload, engine=engine, state_dir=str(self.engine.state_dir)).output

    def task_state(self):
        return self.engine.status()['tasks']['c']['state']

    def files(self):
        return sorted(p.name for p in self.reports.iterdir()) if self.reports.exists() else []


class RecordTests(CaptureCase):
    def test_saves_the_message_unchanged_and_reports_the_running_card(self):
        self.assertEqual(self.stop(), {})
        self.assertEqual((self.reports / (self.token + '.md')).read_text(), GOOD)
        self.assertEqual(self.task_state(), 'reported')

    def test_a_task_line_indented_by_the_workflow_still_matches(self):
        self.write_transcript('  Assignment: w1 %s\n  more' % self.token)
        self.stop()
        self.assertEqual(self.task_state(), 'reported')

    def test_the_prose_form_matches_with_indentation_and_a_closing_period(self):
        self.write_transcript('  Worker name w1, assignment token %s. Write your report.' % self.token)
        self.stop()
        self.assertEqual(self.task_state(), 'reported')

    def test_string_content_in_the_first_user_message_is_read(self):
        self.write_transcript('Assignment: w1 %s' % self.token, content_as_string=True)
        self.stop()
        self.assertEqual(self.task_state(), 'reported')

    def test_the_transcript_path_is_derived_when_the_payload_names_none(self):
        sub = self.root / 'proj' / 'sess9' / 'subagents'
        sub.mkdir(parents=True)
        (sub / 'agent-a1.jsonl').write_text(user_line('Assignment: w1 %s' % self.token) + '\n')
        payload = {'agent_id': 'a1', 'agent_type': 'orchestra:critic', 'session_id': 'sess9',
                   'transcript_path': str(self.root / 'proj' / 'sess9.jsonl'), 'last_assistant_message': GOOD}
        handle_event('SubagentStop', payload, engine=self.engine, state_dir=str(self.engine.state_dir))
        self.assertEqual(self.task_state(), 'reported')


class RefusalTests(CaptureCase):
    def test_a_refused_report_blocks_once_with_the_reason_and_keeps_the_file(self):
        with mock.patch.object(type(self.engine), 'report', side_effect=EngineError('Report needs a SELF_REVIEW line')):
            out = self.stop()
        self.assertEqual(out['decision'], 'block')
        self.assertIn('Report needs a SELF_REVIEW line', out['reason'])
        self.assertNotIn('hookSpecificOutput', out)
        self.assertTrue((self.reports / (self.token + '.md')).is_file())

    def test_a_refused_second_report_leaves_the_saved_report_unchanged(self):
        self.stop()
        self.engine.resume_card('main', self.lease, 'c')  # 2.15.2: after a report only `resume` lets a newer one in
        with mock.patch.object(type(self.engine), 'report', side_effect=EngineError('refused')):
            out = self.stop(message='STATUS: ISSUES\nARTIFACT: def456 clean\nNew text.')
        self.assertEqual(out['decision'], 'block')
        self.assertEqual((self.reports / (self.token + '.md')).read_text(), GOOD)

    def test_it_never_blocks_twice(self):
        with mock.patch.object(type(self.engine), 'report', side_effect=EngineError('refused')):
            out = self.stop(active=True)
        self.assertEqual(out, {})
        self.assertTrue((self.reports / (self.token + '.md')).is_file())
        self.assertEqual(self.task_state(), 'running')


class IgnoredTests(CaptureCase):
    def assertIgnored(self, out):
        self.assertEqual(out, {})
        self.assertEqual(self.files(), [])
        self.assertEqual(self.task_state(), 'running')

    def test_a_foreign_agent_type_is_ignored(self):
        self.assertIgnored(self.stop(agent_type='general-purpose'))

    def test_the_orchestrator_type_is_ignored(self):
        self.assertIgnored(self.stop(agent_type='orchestra:orchestrator'))

    def test_no_run_is_ignored(self):
        self.assertIgnored(self.stop(engine=None))

    def test_an_inactive_run_is_ignored(self):
        self.engine.interrupt_active()
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.files(), [])

    def test_an_unknown_token_is_ignored(self):
        self.write_transcript('Assignment: w1 deadbeef')
        self.assertIgnored(self.stop())

    def test_a_wrong_worker_is_ignored(self):
        self.write_transcript('Assignment: other %s' % self.token)
        self.assertIgnored(self.stop())

    def test_an_empty_message_is_ignored(self):
        self.assertIgnored(self.stop(message='  '))

    def test_an_unreadable_transcript_is_ignored(self):
        self.transcript.unlink()
        self.assertIgnored(self.stop())

    def test_an_accepted_card_is_ignored(self):
        self.stop()  # 2.15.2 (F102): a second message while the card is reported is a newer report, not ignored
        self.engine.accept('main', self.lease, 'c')
        (self.reports / (self.token + '.md')).unlink()
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.files(), [])

    def test_a_queued_card_is_ignored(self):
        self.task('q', role='critic', mode='judge', files=[])
        queued = self.engine.status()['tasks']['q']
        self.assertNotEqual(queued['state'], 'running')
        self.write_transcript('Assignment: w1 nothing')
        self.assertIgnored(self.stop())

    def test_a_corrupt_engine_still_answers_empty(self):
        broken = mock.Mock()
        broken.status.side_effect = ValueError('corrupt')
        self.assertEqual(self.stop(engine=broken), {})


class UnmatchedTests(CaptureCase):
    def test_a_message_without_a_readable_assignment_is_saved_as_unmatched(self):
        self.write_transcript('Please look at the code.')
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.files(), ['unmatched-a1.md'])
        self.assertEqual(self.task_state(), 'running')

    def test_a_message_without_status_and_artifact_lines_is_saved_as_unmatched_and_not_recorded(self):
        self.assertEqual(self.stop(message='All done, looks good.'), {})
        self.assertEqual(self.files(), ['unmatched-a1.md'])
        self.assertEqual(self.task_state(), 'running')

    def test_an_unsafe_token_or_agent_id_cannot_leave_the_reports_directory(self):
        self.write_transcript('Assignment: w1 ../../evil')
        self.stop(agent_id='../x')
        self.assertEqual(self.files(), [])
        self.assertFalse((self.engine.state_dir.parent / 'evil.md').exists())


class RegistrationTests(unittest.TestCase):
    def test_claude_json_registers_subagent_stop_for_orchestra_agents(self):
        hooks = json.loads((PLUGIN / 'hooks/claude.json').read_text())['hooks']['SubagentStop']
        self.assertEqual(hooks[0]['matcher'], 'orchestra:.*')
        self.assertIn('run-hook.sh" SubagentStop --harness claude', hooks[0]['hooks'][0]['command'])

    def test_the_command_line_accepts_the_event_and_prints_empty_json_for_junk(self):
        out = io.StringIO()
        with mock.patch('sys.stdin', io.StringIO('not json')), mock.patch('sys.stdout', out):
            self.assertEqual(hooks_module.main(['SubagentStop']), 0)
        self.assertEqual(json.loads(out.getvalue()), {})


if __name__ == '__main__':
    unittest.main()
