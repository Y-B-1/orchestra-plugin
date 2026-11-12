"""Unit tests for Orchestra's hooks: the merge guard, the Stop hook and the goal CLI."""
import io, json, os, signal, subprocess, sys, tempfile, time, unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orchestra'
LEAN = ROOT / 'scripts/lean.py'
sys.path.insert(0, str(ROOT / 'scripts'))
import lean  # noqa: E402


def git(cwd, *args):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)


class Repo(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(lean.SESSION_ENV, None)
        import gate  # the Stop-hook gate condition has its own tests in test_gate.py
        gate_off = mock.patch.object(gate, 'missing', return_value=[])
        gate_off.start()
        self.addCleanup(gate_off.stop)
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.origin, self.repo = base / 'origin.git', base / 'repo'
        git(base, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        git(base, 'init', '-q', '-b', 'main', str(self.repo))
        git(self.repo, 'config', 'user.email', 't@example.com')
        git(self.repo, 'config', 'user.name', 'T')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'init')
        git(self.repo, 'remote', 'add', 'origin', str(self.origin))
        git(self.repo, 'push', '-q', '-u', 'origin', 'main')
        (self.repo / 'sub').mkdir()
        self.cwd = str(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, name, event):
        event.setdefault('cwd', self.cwd)
        out = io.StringIO()
        with redirect_stdout(out):
            {'stop': lean.hook_stop, 'pre-tool-use': lean.hook_pre_tool_use}[name](event)
        text = out.getvalue().strip()
        return json.loads(text) if text else None

    def bash(self, command, **event):
        return self.hook('pre-tool-use', {'tool_name': 'Bash', 'tool_input': {'command': command}, **event})

    def run_cli(self, *args, env=None, stdin=None):
        return subprocess.run([sys.executable, str(LEAN), *args], cwd=self.cwd, capture_output=True, text=True,
                              input=stdin, env={**os.environ, **(env or {})})


class StopTest(Repo):
    REVIEWED = '- [x] review: clean\n'

    def ledger(self, text, session=None):
        lean.state_dir(self.cwd, session, create=True)
        lean.ledger(self.cwd, session).write_text(text)

    def goal(self, state='active', session=None, **kw):
        lean.state_dir(self.cwd, session, create=True)
        lean.goal_file(self.cwd, session).write_text(json.dumps({'state': state, 'text': 't', 'continues': 0, **kw}))

    def feature(self, pushed=False):
        git(self.repo, 'switch', '-q', '-c', 'feature')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work')
        if pushed:
            git(self.repo, 'push', '-q', '-u', 'origin', 'feature')

    def test_no_goal_and_no_ledger_lets_the_session_stop(self):
        self.assertIsNone(self.hook('stop', {}))

    def test_no_goal_reminds_once_about_open_asks(self):
        self.ledger('- [x] A1: done\n- [ ] A2: open\n')
        out = self.hook('stop', {})
        self.assertEqual(out['decision'], 'block')
        self.assertIn('open asks: A2.', out['reason'])
        self.assertIsNone(self.hook('stop', {'stop_hook_active': True}))

    def test_a_goal_blocks_until_every_ask_is_done(self):
        self.goal()
        self.ledger('- [x] A1: done\n- [>] A2: running\n- [~] A3: dropped, out of scope\n')
        out = self.hook('stop', {'stop_hook_active': True})
        self.assertEqual(out['decision'], 'block')
        self.assertIn('in the ledger: A2.', out['reason'])
        self.assertNotIn('A3', out['reason'])

    def test_a_goal_needs_a_ledger(self):
        self.goal()
        self.assertIn('no ask ledger', self.hook('stop', {})['reason'])

    def test_a_goal_needs_the_branch_pushed(self):
        self.goal()
        self.ledger('- [x] A1: done\n' + self.REVIEWED)
        self.feature()
        self.assertIn('not pushed', self.hook('stop', {})['reason'])
        git(self.repo, 'push', '-q', '-u', 'origin', 'feature')
        self.assertIsNone(self.hook('stop', {}))
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'done')

    def test_a_goal_on_github_needs_an_open_pr_with_the_current_head(self):
        """2.15 rule: a run is complete only once an open pull request holds the current head."""
        self.goal()
        self.ledger('- [x] A1: done\n' + self.REVIEWED)
        self.feature(pushed=True)
        head = lean.git('rev-parse', 'HEAD', cwd=self.cwd)
        with mock.patch.object(lean, 'pr_head', return_value=None):
            self.assertIn('no open pull request', self.hook('stop', {})['reason'])
        with mock.patch.object(lean, 'pr_head', return_value='0' * 40):
            self.assertIn('does not hold the current head', self.hook('stop', {})['reason'])
        with mock.patch.object(lean, 'pr_head', return_value=head):
            self.assertIsNone(self.hook('stop', {}))
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'done')

    def test_pr_head_is_unknown_off_github_so_the_push_alone_finishes(self):
        self.assertEqual(lean.pr_head(self.cwd, 'feature'), lean.UNKNOWN)

    def test_a_goal_on_the_default_branch_asks_for_a_feature_branch(self):
        self.goal()
        self.ledger('- [x] A1: done\n' + self.REVIEWED)
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work on main')
        reason = self.hook('stop', {})['reason']
        self.assertIn('create a feature branch', reason)
        self.assertNotIn('not pushed', reason)

    def test_a_goal_on_a_detached_head_says_so(self):
        self.goal()
        self.ledger('- [x] A1: done\n' + self.REVIEWED)
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work on main')
        git(self.repo, 'switch', '-q', '--detach')
        self.assertIn('detached', self.hook('stop', {})['reason'])

    def test_a_goal_needs_changes_committed(self):
        self.goal()
        self.ledger('- [x] A1: done\n' + self.REVIEWED)
        self.feature(pushed=True)
        (self.repo / 'f.txt').write_text('x')
        git(self.repo, 'add', 'f.txt')
        self.assertIn('uncommitted', self.hook('stop', {})['reason'])

    def test_a_goal_stops_blocking_after_the_cap(self):
        self.goal(continues=lean.MAX_CONTINUES)
        self.ledger('- [ ] A1: open\n')
        self.assertNotIn('decision', self.hook('stop', {}))  # only a message to the owner
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'capped')

    def test_a_stopped_goal_lets_the_session_stop(self):
        self.goal(state='stopped')
        self.ledger('- [ ] A1: open\n')
        self.assertIsNone(self.hook('stop', {'stop_hook_active': True}))

    def test_another_sessions_goal_and_ledger_do_not_hold_this_session(self):
        self.goal(session='s-one')
        self.ledger('- [ ] A1: open\n', session='s-one')
        self.assertIsNone(self.hook('stop', {'session_id': 's-two'}))
        self.assertEqual(self.hook('stop', {'session_id': 's-one'})['decision'], 'block')

    def test_a_goal_set_without_a_session_id_is_still_enforced(self):
        self.goal()  # the shared folder, as goal set writes it when Bash has no CLAUDE_CODE_SESSION_ID
        self.ledger('- [ ] A1: open\n')
        out = self.hook('stop', {'session_id': 's-one', 'stop_hook_active': True})
        self.assertIn('Goal not done', out['reason'])

    def test_another_worktree_of_the_repo_does_not_share_a_session_goal(self):
        self.goal(session='s-one')
        self.ledger('- [ ] A1: open\n', session='s-one')
        wt = Path(self.tmp.name) / 'wt'
        git(self.repo, 'worktree', 'add', '-q', '-b', 'other', str(wt))
        self.assertIsNone(self.hook('stop', {'session_id': 's-two', 'cwd': str(wt)}))


    def transcript(self, worker_age=None, finished=False, journal=None):
        """A session transcript path; with worker_age, one subagent transcript last written that many seconds ago,
        whose last assistant turn is finished (end_turn) or still in a tool call."""
        path = Path(self.tmp.name) / 'session.jsonl'
        path.write_text('')
        if worker_age is not None:
            sub = Path(self.tmp.name) / 'session' / 'subagents' / 'workflows' / 'w1'
            sub.mkdir(parents=True, exist_ok=True)
            f = sub / 'agent-a1.jsonl'
            stop = 'end_turn' if finished else 'tool_use'
            f.write_text(json.dumps({'type': 'assistant', 'message': {'role': 'assistant', 'stop_reason': stop}}) + '\n'
                         + json.dumps({'type': 'attachment'}) + '\n')
            when = time.time() - worker_age
            os.utime(f, (when, when))
            if journal is not None:  # what a Workflow writes beside its agents: launched/started/result rows
                (sub / 'journal.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in journal))
        return str(path)

    def test_a_goal_stays_quiet_while_a_background_worker_runs(self):
        """2.15 rule: running workers end the turn quietly; the app wakes the session when one finishes."""
        self.goal()
        self.ledger('- [>] A1: running in a worker\n')
        self.assertIsNone(self.hook('stop', {'transcript_path': self.transcript(worker_age=5)}))
        goal = json.loads(lean.goal_file(self.cwd).read_text())
        self.assertEqual((goal['state'], goal['continues']), ('active', 0))

    def test_a_worker_that_just_finished_does_not_hold_the_goal(self):
        """Review finding: a transcript written seconds ago by a worker whose turn ended means nothing will wake the
        session, so the hook must still prompt."""
        self.goal()
        self.ledger('- [ ] A1: open\n')
        out = self.hook('stop', {'transcript_path': self.transcript(worker_age=5, finished=True)})
        self.assertEqual(out['decision'], 'block')

    def test_editing_an_untracked_file_counts_as_progress(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        (self.repo / 'new.txt').write_text('a')
        self.hook('stop', {})
        self.hook('stop', {'stop_hook_active': True})  # unchanged: quiet
        (self.repo / 'new.txt').write_text('a longer edit')
        self.assertEqual(self.hook('stop', {})['decision'], 'block')

    def test_editing_an_untracked_file_counts_from_a_subfolder_too(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        sub = str(self.repo / 'sub')
        (self.repo / 'new.txt').write_text('a')
        self.hook('stop', {'cwd': sub})
        self.hook('stop', {'cwd': sub, 'stop_hook_active': True})  # unchanged: quiet
        (self.repo / 'new.txt').write_text('a longer edit')
        self.assertEqual(self.hook('stop', {'cwd': sub})['decision'], 'block')

    def test_a_worker_transcript_not_written_for_minutes_does_not_hold_the_goal(self):
        self.goal()
        self.ledger('- [>] A1: running in a worker\n')
        out = self.hook('stop', {'transcript_path': self.transcript(worker_age=lean.LIVE_WORKER_SECONDS + 60)})
        self.assertEqual(out['decision'], 'block')

    def test_a_goal_never_sends_the_same_reprompt_twice_for_unchanged_work(self):
        """2.15 rule: a turn that changed nothing since the last continuation ends; it is not prompted again."""
        self.goal()
        self.ledger('- [ ] A1: open\n')
        self.assertEqual(self.hook('stop', {})['decision'], 'block')
        out = self.hook('stop', {'stop_hook_active': True})
        self.assertNotEqual((out or {}).get('decision'), 'block')
        self.assertIn('nothing changed', out['systemMessage'])
        self.assertIsNone(self.hook('stop', {'stop_hook_active': True}))  # quiet from then on, no message spam
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'active')

    def test_a_goal_prompts_again_once_the_work_changed(self):
        self.goal()
        self.ledger('- [ ] A1: open\n- [ ] A2: open\n')
        self.hook('stop', {})
        self.hook('stop', {'stop_hook_active': True})  # unchanged: quiet
        self.ledger('- [x] A1: done\n- [ ] A2: open\n')
        out = self.hook('stop', {})
        self.assertEqual(out['decision'], 'block')
        self.assertIn('in the ledger: A2.', out['reason'])

    def test_a_goal_turn_that_ends_with_a_question_is_told_to_decide(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        out = self.hook('stop', {'last_assistant_message': 'Should I use option A or option B?'})
        self.assertIn('Do not wait for an answer', out['reason'])

    def test_the_open_ask_reminder_stays_quiet_while_a_worker_runs_and_is_not_repeated(self):
        self.ledger('- [ ] A1: open\n')
        self.assertIsNone(self.hook('stop', {'transcript_path': self.transcript(worker_age=5)}))
        self.assertEqual(self.hook('stop', {})['decision'], 'block')
        self.assertIsNone(self.hook('stop', {}))  # a later turn, same ledger: no second reminder

class GoalEndTest(Repo):
    """What ends a goal, which files it reads, and what keeps the Stop hook from crashing or going silent."""
    ledger, goal, feature, transcript, REVIEWED = (StopTest.ledger, StopTest.goal, StopTest.feature,
                                                   StopTest.transcript, StopTest.REVIEWED)
    STARTED = {'type': 'started', 'key': 'k1', 'agentId': 'a1'}

    def test_a_finished_workflow_does_not_mute_the_goal(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        journal = [{'type': 'launched'}, self.STARTED, {'type': 'result', 'key': 'k1', 'agentId': 'a1'}]
        out = self.hook('stop', {'transcript_path': self.transcript(worker_age=5, finished=True, journal=journal)})
        self.assertEqual(out['decision'], 'block')

    def test_a_workflow_agent_without_a_result_keeps_the_goal_quiet(self):
        self.goal()
        self.ledger('- [>] A1: running\n')
        journal = [{'type': 'launched'}, self.STARTED]
        self.assertIsNone(self.hook('stop', {'transcript_path': self.transcript(worker_age=5, journal=journal)}))

    def test_a_stopped_workflow_whose_agent_transcript_went_stale_does_not_mute_the_goal(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        journal = [{'type': 'launched'}, self.STARTED]
        age = lean.LIVE_WORKER_SECONDS + 60
        out = self.hook('stop', {'transcript_path': self.transcript(worker_age=age, journal=journal)})
        self.assertEqual(out['decision'], 'block')

    def test_a_workflow_agent_with_no_transcript_yet_counts_only_while_the_journal_is_new(self):
        self.goal()
        self.ledger('- [>] A1: starting\n')
        path = self.transcript(worker_age=5, journal=[{'type': 'launched'}, self.STARTED])
        sub = Path(self.tmp.name) / 'session' / 'subagents' / 'workflows' / 'w1'
        (sub / 'agent-a1.jsonl').unlink()
        self.assertIsNone(self.hook('stop', {'transcript_path': path}))
        old = time.time() - 300
        os.utime(sub / 'journal.jsonl', (old, old))
        self.assertEqual(self.hook('stop', {'transcript_path': path})['decision'], 'block')

    def test_a_failed_workflow_agent_is_not_running(self):
        self.goal()
        self.ledger('- [ ] A1: open\n')
        journal = [self.STARTED, {'type': 'failed', 'key': 'k1', 'agentId': 'a1'}]
        out = self.hook('stop', {'transcript_path': self.transcript(worker_age=5, finished=True, journal=journal)})
        self.assertEqual(out['decision'], 'block')

    def test_work_without_a_diff_ends_when_the_asks_are_marked(self):
        self.goal()
        self.ledger('- [x] A1: explained how the parser works\n')
        self.assertIsNone(self.hook('stop', {}))
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'done')

    def test_a_branch_with_commits_needs_the_review_line(self):
        self.goal()
        self.ledger('- [x] A1: done\n')
        self.feature(pushed=True)
        self.assertIn('review', self.hook('stop', {})['reason'])
        self.ledger('- [x] A1: done\n- [>] review: round 2\n')
        self.assertIn('open asks in the ledger: review', self.hook('stop', {})['reason'])
        self.ledger('base: main (abc) | branch: feature\n- [x] A1: done\n- [x] review: clean\n')
        self.assertIsNone(self.hook('stop', {}))

    def test_the_ledger_headers_sha_is_the_base_when_it_is_there(self):
        self.goal()
        init = lean.git('rev-parse', 'HEAD', cwd=self.cwd)
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'main moved on')
        git(self.repo, 'switch', '-q', '-c', 'feature')
        self.ledger(f'base: main ({init}) | branch: feature | dirty at start: -\n- [x] A1: done\n')
        self.assertIn('no independent review', self.hook('stop', {})['reason'])

    def test_files_dirty_at_start_do_not_count_as_uncommitted_changes(self):
        self.goal()
        (self.repo / 'owner.txt').write_text('a')
        (self.repo / 'mine.txt').write_text('a')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-q', '-m', 'files')
        (self.repo / 'owner.txt').write_text('owner edit')
        head = lean.git('rev-parse', 'HEAD', cwd=self.cwd)
        self.ledger(f'base: main ({head}) | branch: main | dirty at start: owner.txt, other.txt\n- [x] A1: done\n')
        self.assertIsNone(self.hook('stop', {}))
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'done')
        self.goal()
        (self.repo / 'mine.txt').write_text('my edit')
        self.assertIn('uncommitted', self.hook('stop', {})['reason'])

    def test_session_start_names_every_block(self):
        p = self.run_cli('hook', 'session-start', stdin=json.dumps({'cwd': self.cwd}))
        self.assertIn('Blocked: merging into the default branch, a second Fable critic, and an untyped agent during a run.',
                      p.stdout)

    def test_a_branch_pushed_by_name_counts_as_pushed(self):
        self.goal()
        self.ledger('- [x] A1: done\n' + self.REVIEWED)
        git(self.repo, 'switch', '-q', '-c', 'feat', '--track', 'origin/main')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work')
        self.assertIn('git push -u origin feat', self.hook('stop', {})['reason'])
        git(self.repo, 'push', '-q', 'origin', 'feat')
        self.assertIsNone(self.hook('stop', {}))

    def test_a_ledger_without_ask_lines_does_not_end_a_goal(self):
        self.goal()
        for text in ('', '| A1 | todo |\n', '- [?] A1: odd mark\n'):
            with self.subTest(text=text):
                self.ledger(text)
                self.assertIn('no ask lines', self.hook('stop', {})['reason'])
                lean.goal_file(self.cwd).write_text(json.dumps({'state': 'active', 'continues': 0}))

    def test_star_bullets_and_extra_spaces_are_asks(self):
        self.ledger('*  [ ] A1: open\n')
        self.assertIn('open asks: A1.', self.hook('stop', {})['reason'])

    def test_the_reminder_is_keyed_on_the_ledger_alone(self):
        self.ledger('- [ ] A1: open\n')
        self.assertEqual(self.hook('stop', {})['decision'], 'block')
        (self.repo / 'new.txt').write_text('edit')
        git(self.repo, 'add', 'new.txt')
        git(self.repo, 'commit', '-q', '-m', 'unrelated fix')
        self.assertIsNone(self.hook('stop', {}))
        self.ledger('- [ ] A1: open\n- [ ] A2: open\n')
        self.assertEqual(self.hook('stop', {})['decision'], 'block')

    def test_a_non_utf8_change_and_a_damaged_goal_file_do_not_crash_the_hook(self):
        (self.repo / 'a.txt').write_text('cafe\n')
        git(self.repo, 'add', 'a.txt')
        git(self.repo, 'commit', '-q', '-m', 'a')
        (self.repo / 'a.txt').write_bytes(b'caf\xe9\n')
        self.goal()
        self.ledger('- [ ] A1: open\n')
        self.assertEqual(self.hook('stop', {})['decision'], 'block')
        lean.goal_file(self.cwd).write_text('')
        self.assertIsNone(self.hook('stop', {'session_id': 's-x'}))
        self.assertIsNone(self.hook('stop', {}))

    def test_the_ledger_is_found_after_the_folder_became_a_repository(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / '.orchestra' / 'sessions' / 's-1'
            old.mkdir(parents=True)
            (old / 'asks.md').write_text('- [ ] A1: open\n')
            git(Path(d), 'init', '-q', '-b', 'main')
            self.assertEqual([a[1] for a in lean.open_asks(d, 's-1')], ['A1'])

    def test_a_goal_stops_at_its_own_limit_and_says_so(self):
        self.goal(continues=3, limit=3)
        self.ledger('- [ ] A1: open\n')
        out = self.hook('stop', {})
        self.assertIn('limit of 3', out['systemMessage'])
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'capped')

    def test_goal_set_takes_a_limit_and_status_shows_it(self):
        self.run_cli('goal', 'set', '--limit', '7', 'ship')
        self.assertIn('"limit": 7', self.run_cli('goal', 'status').stdout)
        self.run_cli('goal', 'set', 'ship', env={'ORCHESTRA_GOAL_LIMIT': '9'})
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['limit'], 9)

    def test_goal_stop_from_a_terminal_stops_the_session_goals(self):
        self.goal(session='s-one')
        self.assertIn('stopped 1', self.run_cli('goal', 'stop', 'owner').stdout)
        self.assertEqual(json.loads(lean.goal_file(self.cwd, 's-one').read_text())['state'], 'stopped')
        self.goal(session='s-two')
        self.run_cli('goal', 'stop', '--session', 's-two', 'owner')
        self.assertEqual(json.loads(lean.goal_file(self.cwd, 's-two').read_text())['state'], 'stopped')

    def test_session_start_in_a_repo_creates_no_folder_and_points_at_a_branch(self):
        p = self.run_cli('hook', 'session-start', stdin=json.dumps({'cwd': self.cwd, 'session_id': 's-1'}))
        self.assertIn('new branch', p.stdout)
        self.assertFalse((Path(self.cwd) / '.git' / 'orchestra' / 'sessions' / 's-1').exists())
        git(self.repo, 'switch', '-q', '-c', 'feature')
        p = self.run_cli('hook', 'session-start', stdin=json.dumps({'cwd': self.cwd, 'session_id': 's-1'}))
        self.assertNotIn('new branch', p.stdout)

    def test_the_goal_command_grants_only_its_own_script(self):
        text = (ROOT / 'commands/goal.md').read_text()
        self.assertNotIn('python3:*', text)
        self.assertIn('disable-model-invocation: true', text)


class CliTest(Repo):
    def test_goal_set_status_and_stop(self):
        self.assertIn('Goal set', self.run_cli('goal', 'set', 'ship', 'it').stdout)
        self.assertIn('"active"', self.run_cli('goal', 'status').stdout)
        self.assertIn('Goal stopped: needs a token', self.run_cli('goal', 'stop', 'needs', 'a', 'token').stdout)

    def test_goal_set_on_the_default_branch_says_to_branch(self):
        self.assertIn('create a feature branch', self.run_cli('goal', 'set', 'x').stdout)

    def test_goal_set_writes_to_the_session_the_hooks_read(self):
        self.run_cli('goal', 'set', 'x', env={lean.SESSION_ENV: 's-one'})
        self.assertEqual(json.loads(lean.goal_file(self.cwd, 's-one').read_text())['state'], 'active')
        self.assertFalse(lean.goal_file(self.cwd).exists())

    def test_hooks_read_stdin(self):
        p = self.run_cli('hook', 'pre-tool-use', stdin=json.dumps(
            {'tool_name': 'Bash', 'tool_input': {'command': 'gh pr merge 1'}, 'cwd': self.cwd}))
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_the_ledger_lives_in_the_git_dir(self):
        self.assertTrue(self.run_cli('ledger').stdout.strip().endswith('.git/orchestra/asks.md'))
        self.assertTrue(self.run_cli('ledger', env={lean.SESSION_ENV: 's-one'}).stdout.strip()
                        .endswith('.git/orchestra/sessions/s-one/asks.md'))

    def test_malformed_input_never_crashes(self):
        for stdin in ('not json', '[]', '"x"', json.dumps({'tool_name': 'Bash', 'tool_input': 'x'})):
            for name in ('pre-tool-use', 'stop', 'session-start'):
                with self.subTest(stdin=stdin, hook=name):
                    p = self.run_cli('hook', name, stdin=stdin)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertNotIn('Traceback', p.stderr)
        for args in (['hook'], ['hook', 'bogus'], ['run', '--', 'true'], ['run', 'x', '--', 'true'], ['bogus'],
                     ['run', 'nan', '--', 'true'], ['run', '0', '--', 'true']):
            with self.subTest(args=args):
                p = self.run_cli(*args)
                self.assertEqual(p.returncode, 2)
                self.assertNotIn('Traceback', p.stderr)
        p = self.run_cli('run', '5', '--', 'no-such-command-xyz')
        self.assertEqual(p.returncode, 127)
        self.assertNotIn('Traceback', p.stderr)

    def test_session_start_outside_a_repo_creates_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, str(LEAN), 'hook', 'session-start'], cwd=d, input=json.dumps({'cwd': d}),
                               capture_output=True, text=True)
            self.assertIn('Orchestra is on', p.stdout)
            self.assertEqual(os.listdir(d), [])


@unittest.skipUnless(hasattr(os, 'killpg'), 'process groups are POSIX only')
class RunTest(unittest.TestCase):
    # A marker of its own per test process: check.sh runs two Python versions at once.
    MARK = f'{4000 + os.getpid() % 5000}.{os.getpid() % 97}'

    def alive(self, marker):
        return subprocess.run(['pgrep', '-f', marker], capture_output=True).returncode == 0

    def test_a_timeout_stops_the_command_and_its_children(self):
        p = subprocess.run([sys.executable, str(LEAN), 'run', '1', '--', 'sh', '-c', f'sleep {self.MARK}1 & sleep {self.MARK}1'],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 124)
        self.assertIn('TIMEOUT', p.stderr)
        time.sleep(0.5)
        self.assertFalse(self.alive(f'sleep {self.MARK}1'))

    def test_a_signal_killed_command_exits_128_plus_the_signal(self):
        p = subprocess.run([sys.executable, str(LEAN), 'run', '5', '--', 'sh', '-c', 'kill -9 $$'])
        self.assertEqual(p.returncode, 137)

    def test_stopping_the_caller_stops_the_command(self):
        p = subprocess.Popen([sys.executable, str(LEAN), 'run', '60', '--', 'sleep', f'{self.MARK}2'])
        time.sleep(1)
        self.assertTrue(self.alive(f'sleep {self.MARK}2'))
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)
        time.sleep(0.5)
        self.assertFalse(self.alive(f'sleep {self.MARK}2'))


if __name__ == '__main__':
    unittest.main()
