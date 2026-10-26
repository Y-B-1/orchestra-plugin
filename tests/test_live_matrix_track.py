"""live-matrix track matchers (t1 to t3): they read parsed stream-json events. No Claude session runs."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

PATH = pathlib.Path(__file__).resolve().parent.parent / 'scripts/live-matrix.py'
spec = importlib.util.spec_from_file_location('live_matrix', PATH)
lm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lm)

O = 'python3 /p/scripts/orchestra.py'
LEASED = O + ' --' + 'lease L'


def bash(cmd, sub=False):
    return {'tool': 'Bash', 'cmd': cmd, 'input': json.dumps({'command': cmd}), 'sub': sub, 'error': False, 'text': ''}


def tool(name, text, sub=False):
    return {'tool': name, 'cmd': None, 'input': text, 'sub': sub, 'error': False, 'text': ''}


def ev(*calls, hooks=(), tools=()):
    return {'calls': list(calls), 'hooks': [{'event': e, 'out': o} for e, o in hooks], 'texts': [], 'session': 's', 'tools': list(tools)}


class Words(unittest.TestCase):
    def test_inline_forms(self):
        for cmd in [f'{LEASED} inline A --serial x', f'{O} wave --inline A C --emit', f'{O} do "wave --inline A C"']:
            with self.subTest(cmd=cmd):
                self.assertTrue(lm.ran_inline(ev(bash(cmd)), 'A'))

    def test_inline_rejects(self):
        for cmd in [f'{O} dispatch A', f'{O} inline AB', f'{O} wave --inline B A', 'echo inline A', f'{O} inline C']:
            with self.subTest(cmd=cmd):
                self.assertFalse(lm.ran_inline(ev(bash(cmd)), 'A'))

    def test_inline_ignores_subagent_calls(self):
        self.assertFalse(lm.ran_inline(ev(bash(f'{O} inline A', sub=True)), 'A'))


class Order(unittest.TestCase):
    def test_side_before_accept(self):
        e = ev(bash(f'{O} inline A'), bash(f'{O} dispatch C --serial x'), bash(f'{O} accept A'))
        self.assertEqual(lm.side_start_index(e, 'C'), 1)
        self.assertEqual(lm.accept_index(e, 'A'), 2)

    def test_wave_inline_starts_side_card(self):
        e = ev(bash(f'{O} wave --inline A C --emit'))
        self.assertEqual(lm.side_start_index(e, 'C'), 0)
        self.assertIsNone(lm.side_start_index(e, 'A'))

    def test_agent_assignment_counts(self):
        e = ev(tool('Agent', '{"prompt": "Assignment: orchestra-C tok"}'))
        self.assertEqual(lm.side_start_index(e, 'C'), 0)

    def test_subagent_call_is_not_a_start(self):
        self.assertIsNone(lm.side_start_index(ev(bash(f'{O} dispatch C', sub=True)), 'C'))

    def test_accept_forms(self):
        for cmd in [f'{O} accept A', f'{O} do "report m t f" "accept A"', f'{O} inline A --report f --accept']:
            with self.subTest(cmd=cmd):
                self.assertEqual(lm.accept_index(ev(bash(cmd)), 'A'), 0)
        self.assertIsNone(lm.accept_index(ev(bash(f'{O} accept AB')), 'A'))

    def test_shell_punctuation_ends_a_word(self):
        fn = 'o(){ ' + O + ' "$@"; }; o report main t f; echo "report exit=$?"; o accept A; echo done'
        self.assertEqual(lm.accept_index(ev(bash(fn)), 'A'), 0)
        self.assertEqual(lm.side_start_index(ev(bash('o(){ ' + O + ' "$@"; }; o dispatch C; echo ok')), 'C'), 0)
        self.assertTrue(lm.ran_inline(ev(bash('o(){ ' + O + ' "$@"; }; (o inline A)')), 'A'))


class Writes(unittest.TestCase):
    def test_main_session_write(self):
        self.assertTrue(lm.main_wrote(ev(tool('Write', '{"file_path": "/r/a.txt"}')), 'a.txt'))
        self.assertTrue(lm.main_wrote(ev(bash('echo hi > a.txt')), 'a.txt'))

    def test_subagent_write_does_not_count(self):
        self.assertFalse(lm.main_wrote(ev(tool('Write', '{"file_path": "/r/a.txt"}', sub=True)), 'a.txt'))
        self.assertFalse(lm.main_wrote(ev(tool('Write', '{"file_path": "/r/c.txt"}')), 'a.txt'))

    def test_reading_is_not_writing(self):
        self.assertFalse(lm.main_wrote(ev(tool('Read', '{"file_path": "/r/a.txt"}')), 'a.txt'))


class Hooks(unittest.TestCase):
    def test_track_line_found_in_prompt_hook(self):
        out = json.dumps({'additionalContext': 'Orchestra board: x. Track: you run A; side: C'})
        self.assertTrue(lm.hook_says(ev(hooks=[('UserPromptSubmit', out)]), 'Track: you run A; side: C'))
        self.assertFalse(lm.hook_says(ev(hooks=[('UserPromptSubmit', out)]), 'Track: you run B'))


class BoardLine(unittest.TestCase):
    def test_line_in_a_tool_result_counts(self):
        line = 'Orchestra board: A -> queued. Track: you run A; side: C'
        call = bash(O + ' add A.json')
        call['text'] = line
        self.assertTrue(lm.board_says(ev(call), 'Track: you run A; side: C'))
        self.assertTrue(lm.board_says(ev(hooks=[('Stop', line)]), 'Track: you run A; side: C'))
        self.assertFalse(lm.board_says(ev(bash('echo hi')), 'Track: you run A'))

    def test_subagent_result_does_not_count(self):
        call = bash(O + ' add A.json', sub=True)
        call['text'] = 'Track: you run A; side: C'
        self.assertFalse(lm.board_says(ev(call), 'Track: you run A; side: C'))


class Tasks(unittest.TestCase):
    def test_task_creates_carry_step(self):
        e = ev(tool('TaskCreate', '{"subject": "[ab12] A step 1 builder/implementation"}'),
               tool('TaskCreate', '{"subject": "[ab12] B step 2 builder/implementation"}'))
        self.assertEqual(lm.task_subjects(e, 'TaskCreate'), ['[ab12] A step 1 builder/implementation',
                                                            '[ab12] B step 2 builder/implementation'])
        self.assertTrue(lm.step_of(e, 'A', 1))
        self.assertFalse(lm.step_of(e, 'B', 1))

    def test_task_sync_ran(self):
        self.assertTrue(lm.task_sync_ran(ev(tool('TaskList', '{}'))))
        self.assertTrue(lm.task_sync_ran(ev(tool('TaskUpdate', '{"taskId": "1"}'))))
        self.assertFalse(lm.task_sync_ran(ev(bash('echo TaskCreate'), tool('Write', '{}'))))
        self.assertFalse(lm.task_sync_ran(ev(tool('TaskCreate', '{}', sub=True))))

    def test_task_tools_available(self):
        self.assertTrue(lm.task_tools_available(ev(tools=['Bash', 'TaskCreate', 'TaskUpdate', 'TaskList'])))
        self.assertFalse(lm.task_tools_available(ev(tools=['Bash', 'TaskCreate'])))
        self.assertFalse(lm.task_tools_available(ev()))


class Parse(unittest.TestCase):
    def test_parse_reads_tool_names_from_init(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'r.jsonl'
            p.write_text(json.dumps({'type': 'system', 'subtype': 'init', 'session_id': 's', 'tools': ['Bash', 'TaskList']}) + '\n')
            self.assertEqual(lm.parse(p)['tools'], ['Bash', 'TaskList'])


if __name__ == '__main__':
    unittest.main()


class ScratchpadScenarioTest(unittest.TestCase):
    """2.15.2 LV2: scenario a4 proves the scratchpad delete rule live on a decoy tree, never a real scratchpad."""

    def test_a4_is_registered_and_uses_only_the_decoy_tree(self):
        self.assertIn('a4', lm.SCENARIOS)
        self.assertEqual(lm.DECOY, '/tmp/claude-99999')
        source = PATH.read_text()
        body = source[source.index('def a4_'):source.index('\n\n\ndef ', source.index('def a4_'))]
        self.assertNotIn('getuid', body)
        self.assertNotIn('claude-501', body)
