"""Unit tests for Orchestra's guard (PreToolUse): the merge guard, the one-Fable-critic rule and the model matrix."""
import json, os, sys, time, unittest
from pathlib import Path
from unittest import mock

from tests.test_lean import Repo, git, lean  # noqa: E402


class GuardTest(Repo):
    DENY = ['gh pr merge 3 --squash', 'gh pr -R o/r merge 3', 'gh pr -Ro/r merge 3', 'gh -R o/r pr merge 3',
            'git push origin main', 'git push origin HEAD:main', 'git push origin @',
            'git push -f origin main', 'git push origin +main', 'git push origin :main', 'git push origin --delete main',
            'git push origin refs/heads/main', 'git push origin "refs/heads/*:refs/heads/*"',
            "bash -c 'gh pr merge 4'", "sh -lc 'git push origin main'", 'eval "git push origin main"',
            'npm test && gh pr merge 5', 'npm test & gh pr merge 5', '(git push origin main)',
            '(cd sub && git push origin main)', 'echo "$(git push origin main)"', 'x=`gh pr merge 6`',
            'git -C . push origin main', 'git --no-pager push origin main', 'git --git-dir=.git push origin main',
            'git --git-dir .git push origin main', 'git -c push.default=current push origin main', 'git push',
            'git push -o ci.skip origin', 'git push --push-option=ci.skip origin main', 'git push --repo=origin main',
            'git push --mirror origin', 'git push --all origin', 'git push --branches origin', 'sudo git push origin main',
            'GIT_TRACE=1 git push origin main', 'env -i git push origin main',
            'gh api -X PUT repos/o/r/pulls/3/merge', 'gh api repos/o/r/merges -f base=main -f head=x',
            "gh api graphql -f query='mutation { mergePullRequest(input:{}) { clientMutationId } }'",
            'gh api -X DELETE repos/o/r/git/refs/heads/main', 'gh api -XDELETE repos/o/r/git/refs/heads/main',
            'gh api --method=PATCH repos/o/r/git/refs/heads/main -f sha=abc -F force=true',
            'gh api -X PUT repos/o/r/contents/x.txt -f message=m -f content=eA== -f branch=main',
            'gh api repos/o/r/git/refs -f ref=refs/heads/main -f sha=abc',
            'gh api -X POST repos/o/r/branches/main/rename -f new_name=old']

    ALLOW = ['git push -u origin feature/x', 'git push origin --delete old-branch', 'git branch -D stale',
             'git worktree remove --force ../wt', 'git worktree prune', 'rm -rf ../old-worktree',
             'gh pr create --title "merge fix" --body x', 'gh pr create --body "then git push origin main (later)"',
             'gh pr view 3 --json mergeable', 'gh pr list', 'gh pr list --search merge', 'echo gh pr merge 3',
             'echo git push origin main', 'grep -rn "git push origin main" docs', 'git merge main',
             'git push origin feature:feature', 'git push --tags', 'npm run build', 'git reset --hard HEAD~1',
             'gh api repos/o/r/git/refs/heads/main', 'gh api -X PATCH repos/o/r/git/refs/heads/feature -f sha=abc',
             'gh api -X DELETE repos/o/r/git/refs/heads/old', 'gh api -X PUT repos/o/r/contents/x -f branch=feature',
             'echo "a (b) {c} & d"', 'git log --oneline -3', 'git push origin main-backup',
             'gh api -X DELETE repos/o/r/git/refs/heads/main-old', 'gh api -X PATCH repos/o/r/git/refs/heads/main.bak -f sha=a',
             'gh api repos/o/r/git/refs -f ref=refs/heads/main-v2 -f sha=a', 'gh api -X PUT repos/o/r/contents/x -f branch=main-docs']

    def test_merges_into_main_are_denied(self):
        for command in self.DENY:
            with self.subTest(command):
                out = self.bash(command)
                self.assertIsNotNone(out, command)
                self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_everything_else_runs(self):
        for command in self.ALLOW:
            with self.subTest(command):
                self.assertIsNone(self.bash(command))

    def test_a_bare_push_from_a_feature_branch_runs(self):
        git(self.repo, 'switch', '-q', '-c', 'feature')
        self.assertIsNone(self.bash('git push'))
        self.assertIsNone(self.bash('git push -o ci.skip origin'))
        self.assertIsNone(self.bash('git push origin @'))
        self.assertIsNotNone(self.bash('git push origin HEAD:main'))

    def test_push_all_runs_without_a_local_default_branch(self):
        git(self.repo, 'switch', '-q', '-c', 'feature')
        git(self.repo, 'branch', '-q', '-D', 'main')
        self.assertIsNone(self.bash('git push --all origin'))
        self.assertIsNotNone(self.bash('git push --mirror origin'))

    def test_the_default_branch_comes_from_the_remote(self):
        git(self.repo, 'branch', '-q', '-m', 'main', 'trunk')
        git(self.repo, 'push', '-q', '-u', 'origin', 'trunk')
        git(self.repo, 'remote', 'set-head', 'origin', 'trunk')
        self.assertIsNotNone(self.bash('git push origin trunk'))
        self.assertIsNone(self.bash('git push origin main'))

    def test_a_missing_cwd_does_not_crash_and_still_denies(self):
        out = self.bash('git push origin main', cwd=str(self.repo / 'gone'))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_other_tools_and_odd_inputs_are_never_checked(self):
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'Edit', 'tool_input': {'command': 'gh pr merge 1'}}))
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'Bash', 'tool_input': {'command': 123}}))
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'Bash', 'tool_input': {}, 'cwd': 5}))


class GuardReachTest(Repo):
    """What the guard sees (wrappers, keywords, -C) and what it must leave alone (text that only mentions)."""
    DENY = ['if gh pr checks 5 --watch; then gh pr merge 5 --squash; fi',
            'for i in 1 2 3; do git push origin HEAD:main && break; sleep 5; done',
            '! gh pr merge 5', 'while ! git push origin feature:main; do sleep 2; done',
            'timeout 60 gh pr merge 5 --squash', 'timeout -s KILL 60 git push origin main',
            'python3 "/x/scripts/lean.py" run 120 -- gh pr merge 5 --squash',
            'python3 /x/scripts/lean.py run 120 -- git push origin HEAD:main',
            'sudo -u bob git push origin main', 'env -u GIT_DIR git push origin main',
            'nice -n 5 git push origin main', 'npx gh pr merge 5', 'npx -y gh pr merge 5', 'bash -ce "gh pr merge 5"',
            'git \\\n  push origin main', 'gh pr \\\n merge 5 --squash', '/usr/bin/git.exe push origin main',
            'bash <<\'EOF\'\ngh pr merge 5\nEOF', 'cat <<EOF\n$(gh pr merge 5)\nEOF',
            'git push origin "$(git branch --show-current)"', 'pushd sub && git push origin main',
            'gh pr comment 12 --body "Do not run `gh pr merge` yet"']  # a shell runs a backtick span in double quotes
    ALLOW = ['gh pr create --title x --body "$(cat <<\'EOF\'\n## Summary\nOwner: merge with `gh pr merge 12 --squash`\nEOF\n)"',
             'git commit -m "$(cat <<\'EOF\'\nGuard: deny `git push origin main`\nEOF\n)"',
             "gh pr comment 12 --body 'Do not run `gh pr merge` yet'",
             "cat > notes.md <<'EOF'\ngit push origin main is denied by the guard\nEOF",
             "gh issue create --title t --body-file - <<'EOF'\nSteps:\ngh pr merge 5\nEOF",
             'gh api repos/o/r/pulls/3/merge', 'gh api repos/o/r/pulls/12/comments --jq ".[] | select(.path==\\"src/merge.ts\\")"',
             'gh api -X POST repos/o/r/pulls/12/comments/99/replies -f body="Fixed in src/merge.ts"',
             "gh api graphql -f query='query { repository { name } }' --jq '.mergePullRequest'",
             'git push origin "refs/heads/feat*:refs/heads/feat*"', 'git push origin feature > main',
             'git push ${REMOTE:-origin} feature', 'timeout 600 gh pr checks 5 --watch',
             'python3 /x/scripts/lean.py run 120 -- npm test', 'sudo -u bob ls', 'echo "$(date)" && ls']

    def test_commands_that_reach_the_default_branch_are_denied(self):
        for command in self.DENY:
            with self.subTest(command):
                self.assertIsNotNone(self.bash(command), command)

    def test_text_that_only_mentions_runs(self):
        for command in self.ALLOW:
            with self.subTest(command):
                self.assertIsNone(self.bash(command), command)

    def test_git_dash_c_is_followed_to_that_checkout(self):
        wt = Path(self.tmp.name) / 'wt'
        git(self.repo, 'worktree', 'add', '-q', '-b', 'feature', str(wt))
        self.assertIsNotNone(self.bash(f'git -C {wt.parent / "repo"} push', cwd=str(wt)))
        self.assertIsNone(self.bash(f'git -C {wt} push -u origin HEAD'))
        self.assertIsNone(self.bash(f'git -C {wt} push'))

    def test_a_read_only_command_spawns_no_git_and_a_push_one(self):
        with mock.patch.object(lean, 'git', wraps=lean.git) as spy:
            self.assertIsNone(self.bash('cat > a.py <<EOF\n' + 'def f():\n    pass\n' * 300 + 'EOF'))
            self.assertIsNone(self.bash('ls | grep x; echo done'))
            self.assertEqual(spy.call_count, 0)
            self.assertIsNone(self.bash('git status && git log -1; git push origin feature'))
            self.assertEqual(spy.call_count, 1)

    def test_powershell_and_an_mcp_merge_tool_are_guarded_too(self):
        out = self.hook('pre-tool-use', {'tool_name': 'PowerShell', 'tool_input': {'command': 'gh pr merge 1'}})
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        out = self.hook('pre-tool-use', {'tool_name': 'mcp__github__merge_pull_request', 'tool_input': {}})
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'mcp__github__get_pull_request', 'tool_input': {}}))


class FableTest(Repo):
    """One Fable critic at a time, and the model matrix during an Orchestra run."""
    CRITIC = 'orchestra:critic-fable'

    def setUp(self):
        super().setUp()
        self.transcript = Path(self.tmp.name) / 's.jsonl'
        self.transcript.write_text('')

    def call(self, tool_input, tool='Agent'):
        return self.hook('pre-tool-use', {'tool_name': tool, 'tool_input': tool_input, 'session_id': 'sess',
                                          'transcript_path': str(self.transcript)})

    def agent(self, type_=None, **kw):
        return self.call({'description': 'd', 'prompt': 'p', **({'subagent_type': type_} if type_ else {}), **kw})

    def script(self, text):
        return self.call({'script': text}, 'Workflow')

    def worker(self, type_, stop='tool_use', age=0):
        d = self.transcript.with_suffix('') / 'subagents'
        d.mkdir(parents=True, exist_ok=True)
        f = d / f'agent-{type_.replace(":", "-")}.jsonl'
        f.write_text(json.dumps({'type': 'assistant', 'message': {'stop_reason': stop}}) + '\n')
        (d / (f.stem + '.meta.json')).write_text(json.dumps({'agentType': type_}))
        os.utime(f, (time.time() - age, time.time() - age))

    def ledger(self, text='- [>] A1: open\n'):
        lean.state_dir(self.cwd, 'sess', create=True)
        lean.ledger(self.cwd, 'sess').write_text(text)

    def denied(self, out, *words):
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        for w in words:
            self.assertIn(w, out['hookSpecificOutput']['permissionDecisionReason'])

    def test_one_critic_call_is_allowed_by_either_tool_name_and_either_type_name(self):
        for tool, name in (('Agent', self.CRITIC), ('Task', 'critic-fable')):
            self.assertIsNone(self.call({'subagent_type': name}, tool))
            (lean.state_dir(self.cwd, 'sess') / 'fable.lock').unlink(missing_ok=True)

    def test_a_second_critic_is_denied_while_one_runs(self):
        self.worker(self.CRITIC)
        self.denied(self.agent(self.CRITIC), 'one Fable critic')

    def test_a_finished_or_stale_critic_does_not_block(self):
        self.worker(self.CRITIC, stop='end_turn')
        self.assertIsNone(self.agent(self.CRITIC))
        (lean.state_dir(self.cwd, 'sess') / 'fable.lock').unlink()
        self.worker(self.CRITIC, age=lean.LIVE_WORKER_SECONDS + 60)
        self.assertIsNone(self.agent(self.CRITIC))

    def test_another_agent_type_running_does_not_block_the_critic(self):
        self.worker('orchestra:builder')
        self.assertIsNone(self.agent(self.CRITIC))

    def test_a_lock_blocks_a_second_call_until_it_is_stale(self):
        self.assertIsNone(self.agent(self.CRITIC))
        self.denied(self.agent(self.CRITIC), 'one Fable critic')
        lock = lean.state_dir(self.cwd, 'sess') / 'fable.lock'
        old = time.time() - 31 * 60
        os.utime(lock, (old, old))
        self.assertIsNone(self.agent(self.CRITIC))

    def test_a_finished_critic_clears_the_lock(self):
        self.assertIsNone(self.agent(self.CRITIC))
        self.worker(self.CRITIC, stop='end_turn')
        self.assertIsNone(self.agent(self.CRITIC))

    def test_a_fable_model_override_on_another_type_is_denied(self):
        self.denied(self.agent('orchestra:builder', model='claude-fable-5-2'), 'critic-fable')
        self.denied(self.agent(None, model='Fable'), 'critic-fable')
        self.assertIsNone(self.agent('orchestra:builder', model='sonnet'))

    def test_a_workflow_may_name_the_critic_once_outside_a_loop(self):
        self.assertIsNone(self.script("const r = await agent('x', {agentType: 'orchestra:critic-fable'})"))

    def test_a_workflow_naming_the_critic_twice_is_denied(self):
        self.denied(self.script("await agent('a', {agentType: 'orchestra:critic-fable'})\n"
                                "await agent('b', {agentType: 'orchestra:critic-fable'})"), 'once', 'critic-fable')

    def test_a_workflow_naming_the_critic_in_a_fan_out_is_denied(self):
        for text in ("await Promise.all(units.map(u => agent(u, {agentType: 'orchestra:critic-fable'})))",
                     "for (const u of units) {\n  await agent(u, {agentType: 'orchestra:critic-fable'})\n}",
                     "await parallel([\n () => agent('a', {\n agentType: 'critic-fable' }) ])"):
            self.denied(self.script(text), 'loop')

    def test_a_workflow_script_file_is_read_and_a_running_critic_denies(self):
        f = Path(self.tmp.name) / 'wf.js'
        f.write_text("agent('a', {agentType: 'critic-fable'}); agent('b', {agentType: 'critic-fable'})")
        self.denied(self.call({'scriptPath': str(f)}, 'Workflow'), 'once')
        f.write_text("agent('a', {agentType: 'critic-fable'})")
        self.worker(self.CRITIC)
        self.denied(self.call({'scriptPath': str(f)}, 'Workflow'), 'one Fable critic')

    def test_the_matrix_is_silent_outside_a_run(self):
        self.assertIsNone(self.agent())
        self.assertIsNone(self.script("agent('x')"))
        self.ledger('- [x] A1: done\n')
        self.assertIsNone(self.agent('general-purpose'))

    def test_in_a_run_an_agent_without_a_type_or_with_an_inherit_type_is_denied(self):
        self.ledger()
        for t in (None, 'general-purpose', 'claude', 'fork'):
            self.denied(self.agent(t), 'orchestra:', 'main session')

    def test_in_a_run_other_agent_types_are_allowed(self):
        self.ledger()
        for t in ('Explore', 'Plan', 'orchestra:builder', 'other-plugin:thing'):
            self.assertIsNone(self.agent(t))

    def test_in_a_run_every_workflow_agent_names_a_type(self):
        self.ledger()
        self.denied(self.script("await agent('x')"), 'agentType', 'main session')
        self.assertIsNone(self.script("await agent('x', {agentType: 'orchestra:builder'})"))
        self.denied(self.script("await agent('x', {agentType: 'orchestra:builder'}); await agent('y')"), 'agentType')

    def test_the_owner_switch_turns_the_matrix_off(self):
        self.ledger()
        os.environ['ORCHESTRA_MATRIX'] = 'off'
        self.assertIsNone(self.agent('general-purpose'))
        self.assertIsNone(self.script("await agent('x')"))

    def test_input_it_does_not_understand_is_allowed(self):
        self.ledger()
        for tool_input in (None, 'x', {'subagent_type': 5, 'model': []}):
            self.assertIsNone(self.call(tool_input))
        for tool_input in (None, 'x', {'script': 5}, {'scriptPath': '/nope'}):
            self.assertIsNone(self.call(tool_input, 'Workflow'))


if __name__ == '__main__':
    unittest.main()
