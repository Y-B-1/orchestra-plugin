"""Unit tests for Orchestra's hooks: the merge guard, the Stop hook and the goal CLI."""
import io, json, subprocess, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orchestra'
sys.path.insert(0, str(ROOT / 'scripts'))
import lean  # noqa: E402


def git(cwd, *args):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)


class Repo(unittest.TestCase):
    def setUp(self):
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

    def bash(self, command):
        return self.hook('pre-tool-use', {'tool_name': 'Bash', 'tool_input': {'command': command}})


class GuardTest(Repo):
    DENY = ['gh pr merge 3 --squash', 'gh pr -R o/r merge 3', 'git push origin main', 'git push origin HEAD:main',
            'git push -f origin main', 'git push origin +main', 'git push origin :main', 'git push origin --delete main',
            'git push origin refs/heads/main', "bash -c 'gh pr merge 4'", 'npm test && gh pr merge 5',
            'gh api -X PUT repos/o/r/pulls/3/merge', 'gh api repos/o/r/merges -f base=main -f head=x',
            "gh api graphql -f query='mutation { mergePullRequest(input:{}) { clientMutationId } }'",
            'git -C . push origin main', 'git push']

    ALLOW = ['git push -u origin feature/x', 'git push origin --delete old-branch', 'git branch -D stale',
             'git worktree remove --force ../wt', 'git worktree prune', 'rm -rf ../old-worktree',
             'gh pr create --title "merge fix" --body x', 'gh pr view 3 --json mergeable', 'gh pr list',
             'git merge main', 'git push origin feature:feature', 'git push --tags', 'npm run build', 'git reset --hard HEAD~1']

    def test_merges_into_main_are_denied(self):
        for command in self.DENY:
            with self.subTest(command):
                out = self.bash(command)
                self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_everything_else_runs(self):
        for command in self.ALLOW:
            with self.subTest(command):
                self.assertIsNone(self.bash(command))

    def test_a_bare_push_from_a_feature_branch_runs(self):
        git(self.repo, 'switch', '-q', '-c', 'feature')
        self.assertIsNone(self.bash('git push'))
        self.assertIsNotNone(self.bash('git push origin HEAD:main'))

    def test_the_default_branch_comes_from_the_remote(self):
        git(self.repo, 'branch', '-q', '-m', 'main', 'trunk')
        git(self.repo, 'push', '-q', '-u', 'origin', 'trunk')
        git(self.repo, 'remote', 'set-head', 'origin', 'trunk')
        self.assertIsNotNone(self.bash('git push origin trunk'))
        self.assertIsNone(self.bash('git push origin main'))

    def test_other_tools_are_never_checked(self):
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'Edit', 'tool_input': {'command': 'gh pr merge 1'}}))


class StopTest(Repo):
    def ledger(self, text):
        lean.ledger(self.cwd).write_text(text)

    def goal(self, state='active', **kw):
        lean.goal_file(self.cwd).write_text(json.dumps({'state': state, 'text': 't', 'continues': 0, **kw}))

    def test_no_goal_and_no_ledger_lets_the_session_stop(self):
        self.assertIsNone(self.hook('stop', {}))

    def test_no_goal_reminds_once_about_open_asks(self):
        self.ledger('- [x] A1: done\n- [ ] A2: open\n')
        out = self.hook('stop', {})
        self.assertEqual(out['decision'], 'block')
        self.assertIn('A2:', out['reason'])
        self.assertIsNone(self.hook('stop', {'stop_hook_active': True}))

    def test_a_goal_blocks_until_every_ask_is_done(self):
        self.goal()
        self.ledger('- [x] A1: done\n- [>] A2: running\n- [~] A3: dropped, out of scope\n')
        out = self.hook('stop', {'stop_hook_active': True})
        self.assertEqual(out['decision'], 'block')
        self.assertIn('A2:', out['reason'])
        self.assertNotIn('A3', out['reason'])

    def test_a_goal_needs_a_ledger(self):
        self.goal()
        self.assertIn('no ask ledger', self.hook('stop', {})['reason'])

    def test_a_goal_needs_the_branch_pushed(self):
        self.goal()
        self.ledger('- [x] A1: done\n')
        git(self.repo, 'switch', '-q', '-c', 'feature')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work')
        self.assertIn('not pushed', self.hook('stop', {})['reason'])
        git(self.repo, 'push', '-q', '-u', 'origin', 'feature')
        self.assertIsNone(self.hook('stop', {}))
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'done')

    def test_a_goal_needs_changes_committed(self):
        self.goal()
        self.ledger('- [x] A1: done\n')
        (self.repo / 'f.txt').write_text('x')
        git(self.repo, 'add', 'f.txt')
        self.assertIn('uncommitted', self.hook('stop', {})['reason'])

    def test_a_goal_stops_blocking_after_the_cap(self):
        self.goal(continues=lean.MAX_CONTINUES)
        self.ledger('- [ ] A1: open\n')
        self.assertIsNone(self.hook('stop', {}))
        self.assertEqual(json.loads(lean.goal_file(self.cwd).read_text())['state'], 'capped')

    def test_a_stopped_goal_lets_the_session_stop(self):
        self.goal(state='stopped')
        self.ledger('- [ ] A1: open\n')
        self.assertIsNone(self.hook('stop', {'stop_hook_active': True}))


class CliTest(Repo):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/lean.py'), *args], cwd=self.cwd,
                              capture_output=True, text=True)

    def test_goal_set_status_and_stop(self):
        self.assertIn('Goal set', self.run_cli('goal', 'set', 'ship', 'it').stdout)
        self.assertIn('"active"', self.run_cli('goal', 'status').stdout)
        self.assertIn('Goal stopped: needs a token', self.run_cli('goal', 'stop', 'needs', 'a', 'token').stdout)

    def test_hooks_read_stdin(self):
        p = subprocess.run([sys.executable, str(ROOT / 'scripts/lean.py'), 'hook', 'pre-tool-use'], cwd=self.cwd,
                           input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': 'gh pr merge 1'}, 'cwd': self.cwd}),
                           capture_output=True, text=True)
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_the_ledger_lives_in_the_git_dir(self):
        self.assertTrue(self.run_cli('ledger').stdout.strip().endswith('.git/orchestra/asks.md'))


if __name__ == '__main__':
    unittest.main()
