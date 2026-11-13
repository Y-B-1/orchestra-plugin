"""Unit tests for Orchestra's Stop hook, SessionStart text, goal CLI and bounded runner."""
import io, json, os, signal, subprocess, sys, tempfile, time, unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tests.support import LEAN, ROOT, RepoCase, git, lean, transcript

REVIEWED = '- [x] review: clean\n'
STARTED = {'type': 'started', 'key': 'k1', 'agentId': 'a1'}
ENDED = {'type': 'result', 'key': 'k1', 'agentId': 'a1'}


class Repo(RepoCase):
    def setUp(self):
        super().setUp()
        import gate  # the Stop-hook gate condition has its own tests in test_gate.py
        gate_off = mock.patch.object(gate, 'missing', return_value=[])
        gate_off.start()
        self.addCleanup(gate_off.stop)

    def ledger(self, text, session=None):
        lean.state_dir(self.cwd, session, create=True)
        lean.ledger(self.cwd, session).write_text(text)

    def goal(self, state='active', session=None, **kw):
        lean.state_dir(self.cwd, session, create=True)
        lean.goal_file(self.cwd, session).write_text(json.dumps({'state': state, 'text': 't', 'continues': 0, **kw}))

    def goal_state(self, session=None):
        return json.loads(lean.goal_file(self.cwd, session).read_text())['state']

    def stop(self, **event):
        return self.hook('stop', event)

    def feature(self, pushed=False):
        git(self.repo, 'switch', '-q', '-c', 'feature')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work')
        if pushed:
            git(self.repo, 'push', '-q', '-u', 'origin', 'feature')


class StopTest(Repo):
    def test_no_goal_reminds_once_per_ledger_state(self):
        self.assertIsNone(self.stop())  # no ledger at all
        self.ledger('- [x] A1: done\n- [ ] A2: open\n')
        self.assertIsNone(self.stop(transcript_path=transcript(self.tmp.name, worker_age=5)))  # a worker runs: quiet, not used up
        out = self.stop()
        self.assertEqual(out['decision'], 'block')
        self.assertIn('open asks: A2.', out['reason'])
        self.assertIsNone(self.stop())  # same ledger: no second reminder, whatever else changed
        (self.repo / 'new.txt').write_text('edit')
        git(self.repo, 'add', 'new.txt')
        git(self.repo, 'commit', '-q', '-m', 'unrelated fix')
        self.assertIsNone(self.stop())
        self.ledger('- [ ] A2: open\n- [ ] A3: open\n')
        self.assertEqual(self.stop()['decision'], 'block')
        self.ledger('- [ ] A4: open\n')
        self.assertIsNone(self.stop(stop_hook_active=True))  # a continuation of a stop hook is never reminded

    def test_ledger_grammar_decides_what_a_goal_waits_for(self):
        """(ledger text, text the block reason holds or None when the goal ends, text it must not hold)"""
        rows = [
            ('- [x] A1: done\n- [>] A2: running\n- [~] A3: dropped, out of scope\n', 'in the ledger: A2.', 'A3'),
            ('*  [ ] A1: open\n', 'in the ledger: A1.', ''),
            ('- [~] A1: dropped\n', None, ''),
            ('- [x] A1: explained how the parser works\n', None, ''),
            (None, 'no ask ledger', ''),
            ('', 'no ask lines', ''),
            ('| A1 | todo |\n', 'no ask lines', ''),
            ('- [?] A1: odd mark\n', 'no ask lines', ''),
        ]
        for text, holds, lacks in rows:
            with self.subTest(text=text):
                self.goal()
                lean.ledger(self.cwd).unlink(missing_ok=True)
                if text is not None:
                    self.ledger(text)
                out = self.stop(stop_hook_active=True)
                if holds is None:
                    self.assertIsNone(out)
                    self.assertEqual(self.goal_state(), 'done')
                else:
                    self.assertEqual(out['decision'], 'block')
                    self.assertIn(holds, out['reason'])
                    if lacks:
                        self.assertNotIn(lacks, out['reason'])

    def test_a_goal_stops_blocking_at_its_cap_and_says_so(self):
        for goal, text in ((dict(continues=lean.MAX_CONTINUES), None), (dict(continues=3, limit=3), 'limit of 3')):
            with self.subTest(goal=goal):
                self.goal(**goal)
                self.ledger('- [ ] A1: open\n')
                out = self.stop()
                self.assertNotIn('decision', out)  # only a message to the owner
                self.assertIn(text or f'limit of {lean.MAX_CONTINUES}', out['systemMessage'])
                self.assertIn('A1', out['systemMessage'])
                self.assertEqual(self.goal_state(), 'capped')

    def test_the_last_allowed_stop_attempt_still_blocks(self):
        self.goal(continues=2, limit=3)
        self.ledger('- [ ] A1: open\n')
        self.assertEqual(self.stop()['decision'], 'block')

    def test_only_this_sessions_active_goal_holds_it(self):
        self.goal(state='stopped')
        self.ledger('- [ ] A1: open\n')
        self.assertIsNone(self.stop(stop_hook_active=True))
        self.goal(session='s-one')
        self.ledger('- [ ] A1: open\n', session='s-one')
        self.assertEqual(self.stop(session_id='s-one')['decision'], 'block')
        # s-two has no goal of its own and the shared goal here is stopped
        self.assertIsNone(self.stop(session_id='s-two', stop_hook_active=True))
        # a goal set where Bash had no session id sits in the shared folder and still holds a session
        self.goal()
        self.assertIn('Goal not done', self.stop(session_id='s-two', stop_hook_active=True)['reason'])

    def test_an_unchanged_turn_is_not_prompted_twice(self):
        self.goal()
        self.ledger('- [ ] A1: open\n- [ ] A2: open\n')
        self.assertEqual(self.stop()['decision'], 'block')
        out = self.stop(stop_hook_active=True)
        self.assertNotIn('decision', out)
        self.assertIn('nothing changed', out['systemMessage'])
        self.assertIsNone(self.stop(stop_hook_active=True))  # quiet from then on, no message spam
        self.assertEqual(self.goal_state(), 'active')
        self.ledger('- [x] A1: done\n- [ ] A2: open\n')  # the work changed
        out = self.stop()
        self.assertEqual(out['decision'], 'block')
        self.assertIn('in the ledger: A2.', out['reason'])

    def test_editing_an_untracked_file_counts_as_progress_from_any_folder(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        (self.repo / 'new.txt').write_text('a')
        for cwd in (self.cwd, str(self.repo / 'sub')):
            with self.subTest(cwd=cwd):
                self.stop(cwd=cwd)
                self.assertNotIn('decision', self.stop(cwd=cwd, stop_hook_active=True) or {})  # unchanged
                (self.repo / 'new.txt').write_text('a longer edit' + cwd)
                self.assertEqual(self.stop(cwd=cwd)['decision'], 'block')

    def test_a_turn_that_ends_with_a_question_is_told_to_decide(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        out = self.stop(last_assistant_message='Should I use option A or option B?')
        self.assertIn('Do not wait for an answer', out['reason'])
        self.assertIn(f'python3 "{lean.__file__}" goal stop REASON', out['reason'])  # the way out when only the owner can unblock it

    def test_a_running_worker_keeps_the_goal_quiet_and_a_gone_one_does_not(self):
        """The app wakes the session when a worker finishes. (worker transcript age, finished turn, journal rows,
        remove the agent transcript, journal age) -> quiet or blocked."""
        stale = lean.LIVE_WORKER_SECONDS + 60
        rows = [
            (dict(worker_age=5), True, 'tool call in progress'),
            (dict(worker_age=5, finished=True), False, 'turn ended'),
            (dict(worker_age=stale), False, 'not written for minutes'),
            (dict(worker_age=5, journal=[STARTED]), True, 'workflow agent without a result'),
            (dict(worker_age=5, finished=True, journal=[{'type': 'launched'}, STARTED, ENDED]), False, 'workflow finished'),
            (dict(worker_age=5, finished=True, journal=[STARTED, {**ENDED, 'type': 'failed'}]), False, 'workflow agent failed'),
            (dict(worker_age=stale, journal=[STARTED]), False, 'workflow stopped, transcript stale'),
            (dict(worker_age=5, journal=[STARTED], no_agent=True), True, 'agent starting, journal new'),
            (dict(worker_age=5, journal=[STARTED], no_agent=True, journal_age=300), False, 'agent starting, journal old'),
        ]
        for kw, quiet, why in rows:
            with self.subTest(why):
                kw = dict(kw)
                no_agent, journal_age = kw.pop('no_agent', False), kw.pop('journal_age', 0)
                self.goal()
                self.ledger('- [>] A1: running in a worker\n')
                path = transcript(self.tmp.name, **kw)
                sub = Path(self.tmp.name) / 'session' / 'subagents' / 'workflows' / 'w1'
                if no_agent:
                    (sub / 'agent-a1.jsonl').unlink()
                if journal_age:
                    old = time.time() - journal_age
                    os.utime(sub / 'journal.jsonl', (old, old))
                out = self.stop(transcript_path=path)
                if quiet:
                    self.assertIsNone(out)
                    self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['continues'], 0)
                else:
                    self.assertEqual(out['decision'], 'block')

    def test_commits_need_the_review_line_and_then_the_goal_ends(self):
        self.goal()
        self.ledger('- [x] A1: done\n')
        self.feature()
        self.assertIn('no independent review', self.stop()['reason'])
        self.ledger('- [x] A1: done\n- [>] review: round 2\n')
        self.assertIn('open asks in the ledger: review', self.stop()['reason'])
        self.ledger('base: main (abc) | branch: feature\n- [x] A1: done\n' + REVIEWED)  # no remote: nothing left to push
        self.assertIsNone(self.stop())
        self.assertEqual(self.goal_state(), 'done')

    def test_the_ledger_headers_sha_is_the_base_when_it_is_there(self):
        self.goal()
        init = lean.git('rev-parse', 'HEAD', cwd=self.cwd)
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'main moved on')
        git(self.repo, 'switch', '-q', '-c', 'feature')
        self.ledger(f'base: main ({init}) | branch: feature | dirty at start: -\n- [x] A1: done\n')
        self.assertIn('no independent review', self.stop()['reason'])

    def test_files_dirty_at_start_do_not_count_as_uncommitted_changes(self):
        self.goal()
        for name in ('owner.txt', 'mine.txt'):
            (self.repo / name).write_text('a')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-q', '-m', 'files')
        (self.repo / 'owner.txt').write_text('owner edit')
        head = lean.git('rev-parse', 'HEAD', cwd=self.cwd)
        self.ledger(f'base: main ({head}) | branch: main | dirty at start: owner.txt, other.txt\n- [x] A1: done\n')
        self.assertIsNone(self.stop())
        self.assertEqual(self.goal_state(), 'done')
        self.goal()
        (self.repo / 'mine.txt').write_text('my edit')
        self.assertIn('uncommitted', self.stop()['reason'])

    def test_a_non_utf8_change_and_a_damaged_goal_file_do_not_crash_the_hook(self):
        (self.repo / 'a.txt').write_text('cafe\n')
        git(self.repo, 'add', 'a.txt')
        git(self.repo, 'commit', '-q', '-m', 'a')
        (self.repo / 'a.txt').write_bytes(b'caf\xe9\n')
        self.goal()
        self.ledger('- [ ] A1: open\n')
        self.assertEqual(self.stop()['decision'], 'block')
        lean.goal_file(self.cwd).write_text('')
        self.assertIsNone(self.stop(session_id='s-x'))
        self.assertIsNone(self.stop())

    def test_the_ledger_is_found_after_the_folder_became_a_repository(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / '.orchestra' / 'sessions' / 's-1'
            old.mkdir(parents=True)
            (old / 'asks.md').write_text('- [ ] A1: open\n')
            git(Path(d), 'init', '-q', '-b', 'main')
            self.assertEqual([a[1] for a in lean.open_asks(d, 's-1')], ['A1'])


class PushTest(Repo):
    """The pushed-branch and pull-request conditions, against a real origin."""
    ORIGIN = True

    def setUp(self):
        super().setUp()
        self.goal()
        self.ledger('- [x] A1: done\n' + REVIEWED)

    def test_the_default_branch_and_a_detached_head_are_not_places_to_finish(self):
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work on main')
        reason = self.stop()['reason']
        self.assertIn('create a feature branch', reason)
        self.assertNotIn('not pushed', reason)
        git(self.repo, 'switch', '-q', '--detach')
        self.assertIn('detached', self.stop()['reason'])

    def test_staged_changes_are_uncommitted(self):
        self.feature(pushed=True)
        (self.repo / 'f.txt').write_text('x')
        git(self.repo, 'add', 'f.txt')
        self.assertIn('uncommitted', self.stop()['reason'])

    def test_a_branch_pushed_by_name_counts_as_pushed(self):
        git(self.repo, 'switch', '-q', '-c', 'feat', '--track', 'origin/main')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work')
        self.assertIn('git push -u origin feat', self.stop()['reason'])
        git(self.repo, 'push', '-q', 'origin', 'feat')
        self.assertIsNone(self.stop())  # the remote is not GitHub, so the pull request is unknown and never holds
        self.assertEqual(self.goal_state(), 'done')
        self.assertEqual(lean.pr_head(self.cwd, 'feat'), lean.UNKNOWN)

    def test_a_goal_on_github_needs_an_open_pr_with_the_current_head(self):
        self.feature(pushed=True)
        head = lean.git('rev-parse', 'HEAD', cwd=self.cwd)
        for pr, text in ((None, 'no open pull request'), ('0' * 40, 'does not hold the current head'), (head, None)):
            with self.subTest(pr=pr), mock.patch.object(lean, 'pr_head', return_value=pr):
                out = self.stop()
                if text:
                    self.assertIn(text, out['reason'])
                else:
                    self.assertIsNone(out)
                    self.assertEqual(self.goal_state(), 'done')


class CliTest(Repo):
    def cli(self, *args, env=None, stdin='', cwd=None):
        """lean.main() in this process: (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        old_cwd = os.getcwd()
        os.chdir(cwd or self.cwd)
        try:
            with mock.patch.object(sys, 'argv', ['lean.py', *args]), mock.patch.object(sys, 'stdin', io.StringIO(stdin)), \
                    mock.patch.dict(os.environ, env or {}), redirect_stdout(out), redirect_stderr(err):
                rc = lean.main()
        finally:
            os.chdir(old_cwd)
        return rc, out.getvalue(), err.getvalue()

    def start(self, **event):
        return self.cli('hook', 'session-start', stdin=json.dumps({'cwd': self.cwd, **event}))

    def test_goal_set_status_and_stop(self):
        rc, out, _ = self.cli('goal', 'set', 'ship', 'it')
        self.assertEqual(rc, 0)
        self.assertIn('Goal set; it ends after 60 stop attempts', out)
        self.assertIn('create a feature branch', out)  # the repo is on main
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['text'], 'ship it')
        self.assertIn('"active"', self.cli('goal', 'status')[1])
        self.assertIn('Goal stopped: needs a token (stopped 1)', self.cli('goal', 'stop', 'needs', 'a', 'token')[1])
        git(self.repo, 'switch', '-q', '-c', 'feature')
        self.assertNotIn('create a feature branch', self.cli('goal', 'set', 'x')[1])

    def test_goal_set_takes_a_limit_from_a_flag_or_the_environment(self):
        for args, env, limit in ((['--limit', '7', 'ship'], {}, 7), (['ship'], {'ORCHESTRA_GOAL_LIMIT': '9'}, 9),
                                 (['--limit', '0', 'ship'], {}, 60), (['--limit', 'many', 'ship'], {}, 60)):
            with self.subTest(args=args, env=env):
                self.cli('goal', 'set', *args, env=env)
                self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['limit'], limit)
        self.assertIn('"limit": 60', self.cli('goal', 'status')[1])

    def test_goal_set_and_stop_target_the_session_the_hooks_read(self):
        self.cli('goal', 'set', 'x', env={lean.SESSION_ENV: 's-one'})
        self.assertEqual(self.goal_state('s-one'), 'active')
        self.assertFalse(lean.goal_file(self.cwd).exists())
        for name in ('s-two', 's-three', 's-four'):
            self.goal(session=name)
        self.cli('goal', 'stop', '--session', 's-three', 'owner')
        self.assertEqual([self.goal_state(s) for s in ('s-one', 's-two', 's-three', 's-four')],
                         ['active', 'active', 'stopped', 'active'])
        self.assertIn('stopped 3', self.cli('goal', 'stop', 'owner', env={lean.SESSION_ENV: ''})[1])  # a terminal ends them all
        self.assertEqual([self.goal_state(s) for s in ('s-one', 's-two', 's-four')], ['stopped'] * 3)

    def test_the_ledger_lives_in_the_git_dir(self):
        self.assertTrue(self.cli('ledger')[1].strip().replace('\\', '/').endswith('.git/orchestra/asks.md'))  # Windows prints backslashes
        out = self.cli('ledger', env={lean.SESSION_ENV: 's-one'})[1]
        self.assertTrue(out.strip().replace('\\', '/').endswith('.git/orchestra/sessions/s-one/asks.md'))

    def test_session_start_names_the_blocks_and_creates_no_folder(self):
        rc, out, _ = self.start(session_id='s-1')
        self.assertEqual(rc, 0)
        self.assertIn('Blocked: merging into the default branch, a second Fable critic, and an untyped agent during a run.', out)
        self.assertIn('new branch', out)  # on main
        self.assertFalse((self.repo / '.git' / 'orchestra').exists())
        git(self.repo, 'switch', '-q', '-c', 'feature')
        self.assertNotIn('new branch', self.start(session_id='s-1')[1])

    def test_session_start_outside_a_repo_creates_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _, out, _ = self.cli('hook', 'session-start', stdin=json.dumps({'cwd': d}), cwd=d)
            self.assertIn('Orchestra is on', out)
            self.assertEqual(os.listdir(d), [])

    def test_malformed_input_and_bad_arguments_never_crash(self):
        for stdin in ('not json', '[]', '"x"', json.dumps({'tool_name': 'Bash', 'tool_input': 'x'})):
            for name in ('pre-tool-use', 'stop', 'session-start'):
                with self.subTest(stdin=stdin, hook=name):
                    rc, _, err = self.cli('hook', name, stdin=stdin)
                    self.assertEqual((rc, err), (0, ''))
        for args in (['hook'], ['hook', 'bogus'], ['run', '--', 'true'], ['run', 'x', '--', 'true'], ['bogus'],
                     ['run', 'nan', '--', 'true'], ['run', '0', '--', 'true'], ['run', '5', 'true']):
            with self.subTest(args=args):
                rc, _, err = self.cli(*args)
                self.assertEqual(rc, 2)
                self.assertIn('Orchestra', err)
        rc, _, err = self.cli('run', '5', '--', 'no-such-command-xyz')
        self.assertEqual(rc, 127)
        self.assertIn('cannot start', err)

    def test_the_goal_command_grants_only_its_own_script(self):
        text = (ROOT / 'commands/goal.md').read_text()
        self.assertNotIn('python3:*', text)
        self.assertIn('disable-model-invocation: true', text)


def run_lean(*args, stdin=None, **kw):
    return subprocess.run([sys.executable, str(LEAN), *args], capture_output=True, text=True, input=stdin, **kw)


def wait_for(condition, seconds=5):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


class ProcessTest(unittest.TestCase):
    """The parts that need a real process: the entry point and stdin, and the bounded runner's kills."""
    # A marker of its own per test process: check.sh runs two Python versions at once.
    MARK = f'{4000 + os.getpid() % 5000}.{os.getpid() % 97}'

    def alive(self, marker):
        return subprocess.run(['pgrep', '-f', '^' + marker], capture_output=True).returncode == 0  # the sleep itself, not a parent that spells it

    def test_the_entry_point_reads_the_hook_event_from_stdin(self):
        event = {'tool_name': 'Bash', 'tool_input': {'command': 'gh pr merge 1'}, 'cwd': str(ROOT)}
        p = run_lean('hook', 'pre-tool-use', stdin=json.dumps(event))
        self.assertEqual((p.returncode, p.stderr), (0, ''))
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    @unittest.skipUnless(hasattr(os, 'killpg'), 'process groups are POSIX only')
    def test_a_timeout_stops_the_command_and_its_children(self):
        sleeper = f'sleep {self.MARK}1'
        p = run_lean('run', '1', '--', 'sh', '-c', f'{sleeper} & {sleeper}')
        self.assertEqual(p.returncode, 124)
        self.assertIn('TIMEOUT', p.stderr)
        self.assertTrue(wait_for(lambda: not self.alive(sleeper)))

    def test_exit_codes_pass_through_and_a_signal_death_is_128_plus_the_signal(self):
        self.assertEqual(run_lean('run', '5', '--', 'sh', '-c', 'exit 3').returncode, 3)
        if hasattr(os, 'killpg'):  # Windows has no signals: its wait status is not a signal number
            self.assertEqual(run_lean('run', '5', '--', 'sh', '-c', 'kill -9 $$').returncode, 137)

    @unittest.skipUnless(hasattr(os, 'killpg'), 'process groups are POSIX only')
    def test_stopping_the_caller_stops_the_command(self):
        sleeper = f'sleep {self.MARK}2'
        p = subprocess.Popen([sys.executable, str(LEAN), 'run', '60', '--', 'sleep', f'{self.MARK}2'])
        self.assertTrue(wait_for(lambda: self.alive(sleeper)))
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=10), 128 + signal.SIGTERM)
        self.assertTrue(wait_for(lambda: not self.alive(sleeper)))


class Owns(RepoCase):
    """`lean.py owns COMMIT -- PATH...` against a real repository."""

    def owns(self, commit, *paths, cwd=None):
        return subprocess.run([sys.executable, str(LEAN), 'owns', commit, '--', *paths], cwd=cwd or self.cwd,
                              capture_output=True, text=True)

    def commit(self, *files):
        for f in files:
            (self.repo / f).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / f).write_text(f)
            git(self.repo, 'add', f)
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'c')
        return git(self.repo, 'rev-parse', 'HEAD')

    def test_a_commit_inside_the_unit_passes_and_one_outside_names_the_file(self):
        inside = self.commit('a/x.py', 'b.txt')
        self.assertEqual(self.owns(inside, 'a/', 'b.txt').returncode, 0)
        outside = self.commit('a/y.py', 'c/z.py')
        r = self.owns(outside, 'a/')
        self.assertEqual((r.returncode, r.stdout.splitlines()), (1, ['c/z.py']))

    def test_a_glob_crosses_folders_only_with_two_stars(self):
        deep = self.commit('t/a/b/test_x.py')
        self.assertEqual(self.owns(deep, 't/**/*.py').returncode, 0)
        self.assertEqual(self.owns(deep, 't/*.py').returncode, 1)

    def test_a_rename_out_of_the_unit_fails_on_the_new_side(self):
        self.commit('a/x.py')
        (self.repo / 'c').mkdir()
        git(self.repo, 'mv', 'a/x.py', 'c/x.py')
        git(self.repo, 'commit', '-q', '-m', 'move')
        moved = git(self.repo, 'rev-parse', 'HEAD')
        r = self.owns(moved, 'a/')
        self.assertEqual((r.returncode, r.stdout.splitlines()), (1, ['c/x.py']))

    def test_a_range_checks_every_commit_in_it(self):
        base = self.commit('a/1.py')
        self.commit('a/2.py')
        self.commit('c/3.py')
        r = self.owns(f'{base}..HEAD', 'a/')
        self.assertEqual((r.returncode, r.stdout.splitlines()), (1, ['c/3.py']))
        self.assertEqual(self.owns(f'{base}..HEAD', 'a/', 'c/').returncode, 0)

    def test_a_folder_named_without_a_slash_owns_everything_under_it(self):
        deep = self.commit('docs/hooks.md', 'plugins/s/x.py')
        self.assertEqual(self.owns(deep, 'docs', 'plugins/s').returncode, 0)
        sibling = self.commit('docs2/y.md')
        r = self.owns(sibling, 'docs')
        self.assertEqual((r.returncode, r.stdout.splitlines()), (1, ['docs2/y.md']))

    def test_bad_input_exits_2_with_a_message(self):
        head = self.commit('a/1.py')
        empty_range = f'{head}..{head}'
        for args, cwd in [(('nope', 'a/'), None), ((head,), None), ((head, 'a/'), self.tmp.name), ((empty_range, 'a/'), None),
                          ((f'{head}~0..{head}~0', 'a/'), None), ((head, ''), None)]:
            r = self.owns(*args, cwd=cwd)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn('owns:', r.stderr)


class E2eDoctorUsage(unittest.TestCase):
    def test_help_lists_e2e_doctor_and_a_bad_flag_exits_2(self):
        r = subprocess.run([sys.executable, str(LEAN), 'e2e-doctor', '--bogus'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('lean.py e2e-doctor [--config PATH]', r.stderr)


if __name__ == '__main__':
    unittest.main()
