"""F62: a Workflow agent's transcript starts with the harness's relayed user request; the Assignment line is in the
second, indented user message (the computed task). Capture must still find it."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_capture import GOOD, CaptureCase, user_line

RELAYED = ('[Workflow harness — user request] The harness relays, verbatim and indented below, the user request that '
           'triggered this workflow run.\n  Start 2.14.2 here: build them test first, open a PR, no merge.')
COMPUTED = ('[Workflow harness — computed task] The task text below was computed at runtime by a workflow script.\n'
            '  Read your brief at /x/E1.md and do exactly what it says.\n  Assignment: w1 %s\n')


class WorkflowTranscriptTests(CaptureCase):
    def write_lines(self, *texts):
        lines = [user_line(t) for t in texts] + [json.dumps({'type': 'assistant', 'message': {'content': 'x'}})]
        self.transcript.write_text('\n'.join(lines) + '\n')

    def test_the_assignment_in_the_second_user_message_is_found(self):
        self.write_lines(RELAYED, COMPUTED % self.token)
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.task_state(), 'reported')
        self.assertEqual((self.reports / (self.token + '.md')).read_text(), GOOD)

    def test_attachment_and_skill_lines_between_do_not_hide_it(self):
        lines = [user_line(RELAYED), user_line(COMPUTED % self.token)]
        lines += [json.dumps({'type': 'attachment'})] * 3
        lines += [user_line('<command-name>orchestra-worker</command-name>')]
        self.transcript.write_text('\n'.join(lines) + '\n')
        self.stop()
        self.assertEqual(self.task_state(), 'reported')

    def test_an_assignment_naming_no_running_card_is_still_unmatched_or_ignored(self):
        self.write_lines(RELAYED, COMPUTED % 'notarunningtoken0000')
        self.stop()
        self.assertEqual(self.task_state(), 'running')
        self.assertNotIn(self.token + '.md', self.files())

    def test_no_assignment_anywhere_saves_unmatched(self):
        self.write_lines(RELAYED, '[Workflow harness — computed task]\n  Do something.')
        self.stop()
        self.assertEqual(self.task_state(), 'running')
        self.assertIn('unmatched-a1.md', self.files())


if __name__ == '__main__':
    unittest.main()
