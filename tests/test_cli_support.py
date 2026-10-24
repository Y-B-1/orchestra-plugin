"""The refusal log, the `refusals` command and the one-line board delta of the CLI (2.14)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]/'plugins/orchestra'
CLI = PLUGIN/'scripts/orchestra.py'
sys.path.insert(0, str(PLUGIN/'scripts'))

from orchestra_core import cli_support, delta  # noqa: E402

SELF_REVIEW = 'ARTIFACT: fixture\nSELF_REVIEW: '+json.dumps(dict(
    checks=[dict(command='fixture check', exit_code=0)],
    criteria=[dict(criterion='fixture check', met=True, evidence='Inspected fixture.')]))


def view(**states):
    columns = {}
    for ident, state in states.items():
        columns.setdefault(state, []).append(ident)
    return dict(columns=columns, counts={s: len(v) for s, v in columns.items()},
                cards=[dict(id=i, state=s) for i, s in states.items()])


class DeltaUnits(unittest.TestCase):
    def test_no_move_is_none(self):
        self.assertIsNone(delta.delta(view(A='queued'), view(A='queued')))
        self.assertIsNone(delta.delta(None, view(A='queued')))

    def test_a_move_names_id_old_new_and_counts(self):
        line = delta.delta(view(A='queued', B='queued'), view(A='running', B='queued'))
        self.assertIn('A queued>running', line)
        self.assertNotIn('B queued>', line)
        self.assertIn('running 1', line)
        self.assertIn('queued 1', line)
        self.assertNotIn('\n', line)

    def test_a_new_card_is_a_move_from_nothing(self):
        self.assertIn('B ->queued', delta.delta(view(A='queued'), view(A='queued', B='queued')))

    def test_signature_changes_with_state_only(self):
        a, b = view(A='queued'), view(A='running')
        self.assertEqual(delta.signature(a), delta.signature(view(A='queued')))
        self.assertNotEqual(delta.signature(a), delta.signature(b))


class LogUnits(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)/'state'

    def test_no_state_directory_writes_nothing(self):
        cli_support.log_refusal(self.state, ['accept', 'A'], 'nope')
        self.assertFalse(self.state.exists())

    def test_lease_value_is_removed_in_both_spellings(self):
        self.state.mkdir()
        cli_support.log_refusal(self.state, ['--lease', 'SECRET1', 'accept', 'A'], 'nope')
        cli_support.log_refusal(self.state, ['--lease=SECRET2', 'accept', 'B'], 'nope')
        text = (self.state/'refusals.jsonl').read_text()
        self.assertNotIn('SECRET', text)
        entry = json.loads(text.splitlines()[0])
        self.assertEqual(sorted(entry), ['at', 'command', 'error'])
        self.assertIn('accept A', entry['command'])

    def test_log_keeps_the_newest_200_lines(self):
        self.state.mkdir()
        for i in range(205):
            cli_support.log_refusal(self.state, ['accept', 'T%d' % i], 'e')
        lines = (self.state/'refusals.jsonl').read_text().splitlines()
        self.assertEqual(len(lines), 200)
        self.assertIn('T204', lines[-1])
        self.assertIn('T5', lines[0])

    def test_failing_write_is_swallowed(self):
        self.state.mkdir()
        (self.state/'refusals.jsonl').mkdir()  # a directory where the file belongs
        cli_support.log_refusal(self.state, ['accept', 'A'], 'nope')

    def test_read_returns_newest_n(self):
        self.state.mkdir()
        for i in range(5):
            cli_support.log_refusal(self.state, ['accept', 'T%d' % i], 'e')
        got = cli_support.read_refusals(self.state, 2)
        self.assertEqual([e['command'] for e in got], ['accept T3', 'accept T4'])
        self.assertEqual(cli_support.read_refusals(self.state/'none', 2), [])

    def test_seen_record_is_the_prompt_hook_shape(self):
        self.state.mkdir()
        seen = view(A='queued')
        cli_support.store_seen(self.state, seen)
        delta.store(self.state, 'hook-seen.json', seen)
        self.assertEqual(json.loads((self.state/'board-seen.json').read_text()),
                         json.loads((self.state/'hook-seen.json').read_text()))
        self.assertEqual(json.loads((self.state/'board-seen.json').read_text())['cards'], {'A': 'queued'})


class CliRefusals(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='Orchestra cli support ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'repo'
        self.repo.mkdir()
        self.state = self.root/'state'
        for args in (['init', '-b', 'main'], ['config', 'user.name', 'T'], ['config', 'user.email', 't@example.invalid']):
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
        (self.repo/'fixture.txt').write_text('ready\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', 'fixture.txt'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', 'Fixture'], check=True, capture_output=True)

    def run_cli(self, *args, lease=None, expected=0):
        cmd = [sys.executable, str(CLI), '--repo', str(self.repo), '--state', str(self.state)]
        if lease:
            cmd += ['--lease', lease]
        result = subprocess.run(cmd+list(args), capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, expected, result.stderr+result.stdout)
        return result, json.loads(result.stdout if expected == 0 else result.stderr)

    def start(self):
        return self.run_cli('start', '--size', 'medium')[1]['lease']

    def card(self, ident, name):
        task = dict(id=ident, role='builder', mode='implementation', inputs=['fixture outcome'], acceptance=['fixture check'],
                    files=[name], resources=[], dependencies=[], outcome='fixture outcome')
        path = self.root/(ident+'.json')
        path.write_text(json.dumps(task))
        return path

    def test_refusal_is_logged_without_the_lease_and_keeps_its_exit_and_text(self):
        lease = self.start()
        result, body = self.run_cli('accept', 'NOPE', lease=lease, expected=2)
        self.assertEqual(result.stdout, '')
        logged = (self.state/'refusals.jsonl').read_text()
        self.assertNotIn(lease, logged)
        entry = json.loads(logged.splitlines()[-1])
        self.assertEqual(entry['error'], body['error'])
        self.assertIn('accept NOPE', entry['command'])

    def test_refusals_command_prints_the_newest_and_never_writes(self):
        lease = self.start()
        for name in ('X1', 'X2', 'X3'):
            self.run_cli('accept', name, lease=lease, expected=2)
        before = (self.state/'refusals.jsonl').read_text()
        _, got = self.run_cli('refusals', '--last', '2')
        self.assertEqual([e['command'].split()[-1] for e in got['refusals']], ['X2', 'X3'])
        self.assertEqual((self.state/'refusals.jsonl').read_text(), before)

    def test_refusals_runs_without_a_state_directory(self):
        _, got = self.run_cli('refusals')
        self.assertEqual(got['refusals'], [])
        self.assertFalse(self.state.exists())

    def test_refused_command_creates_no_state_directory(self):
        bad = self.root/'policy.json'
        bad.write_text('[]')
        self.run_cli('start', '--size', 'medium', '--policy', str(bad), expected=2)
        self.assertFalse(self.state.exists())
        self.run_cli('accept', 'A', lease='L', expected=2)  # the engine makes the directory; the log still stays away
        self.assertFalse((self.state/'refusals.jsonl').exists())

    def test_unwritable_log_keeps_exit_code_and_error_text(self):
        lease = self.start()
        (self.state/'refusals.jsonl').mkdir()
        result, body = self.run_cli('accept', 'NOPE', lease=lease, expected=2)
        self.assertTrue(body['error'])
        self.assertEqual(result.stderr.count('\n'), 1)

    def test_board_line_appears_only_when_a_card_moved_and_is_stored_after(self):
        lease = self.start()
        _, added = self.run_cli('add', str(self.card('B1', 'one.txt')), lease=lease)
        self.assertIn('B1 ->queued', added['board'])
        self.assertIn('queued 1', added['board'])
        seen = json.loads((self.state/'board-seen.json').read_text())['signature']
        _, dispatched = self.run_cli('dispatch', 'B1', 'worker-B1', '--helper', 'fixture helper', '--serial', 'one', lease=lease)
        self.assertIn('B1 queued>running', dispatched['board'])
        self.assertNotEqual(json.loads((self.state/'board-seen.json').read_text())['signature'], seen)
        self.assertEqual(json.loads((self.state/'board-seen.json').read_text())['cards'], {'B1': 'running'})
        rep = self.root/'rep.txt'
        rep.write_text('Inspected fixture.\n'+SELF_REVIEW+'\n')
        _, reported = self.run_cli('report', 'worker-B1', dispatched['assignment'], str(rep))
        self.assertIn('B1 running>reported', reported['board'])

    def test_no_board_key_when_nothing_moved_and_read_only_never_writes_seen(self):
        lease = self.start()
        for command in ('board', 'status', 'waves'):
            _, out = self.run_cli(command)
            self.assertNotIn('board', out)
        self.run_cli('ready', lease=lease)
        self.assertFalse((self.state/'board-seen.json').exists())

    def test_abbreviated_options_are_refused_and_full_spellings_still_parse(self):
        lease = self.start()
        for argv in (['--leas', lease, 'where'], ['--lea=' + lease, 'where'], ['refusals', '--la', '1'], ['finding', 'list', '--for']):
            result = subprocess.run([sys.executable, str(CLI), '--repo', str(self.repo), '--state', str(self.state), *argv],
                                    capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 2, argv)
            self.assertIn('usage:', result.stderr, argv)
        self.run_cli('where', lease=lease)
        self.run_cli('status', '--full', lease=lease)
        self.run_cli('refusals', '--last', '1')
        self.run_cli('finding', 'list')


if __name__ == '__main__':
    unittest.main()
