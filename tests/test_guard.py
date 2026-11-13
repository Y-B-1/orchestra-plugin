"""Unit tests for Orchestra's guard (PreToolUse): the merge guard, the one-Fable-critic rule and the model matrix."""
import os, shutil, tempfile, time, unittest
from pathlib import Path
from unittest import mock

from tests.support import RepoCase, git, lean, worker


class GuardTest(RepoCase):
    # Commands that reach the default branch: direct, wrapped, chained, quoted, spelled through gh api, or hidden in a shell word.
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
            'gh api -X POST repos/o/r/branches/main/rename -f new_name=old',
            # a redirect written without a space does not hide the branch
            'git push origin main>/dev/null', 'git push origin main>>log', 'git push origin main2>&1',
            'gh pr merge 3>/dev/null', 'git push origin main</dev/null', 'git push origin main> out',
            # wrappers, keywords and heredocs a shell runs
            'if gh pr checks 5 --watch; then gh pr merge 5 --squash; fi',
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
            'gh pr comment 12 --body "Do not run `gh pr merge` yet"',  # a shell runs a backtick span in double quotes
            # a substitution inside a quoted argument must not hide the rest of the command from the check
            'gh api -X PUT repos/o/r/contents/f -f message=m -f content="$(printf x | base64)" -f branch=main',
            'gh api -X PUT repos/o/r/contents/f -f content="`printf x`" -f branch=main',
            'gh api -X PATCH repos/o/r/git/refs/heads/main -f sha="$(git rev-parse HEAD)" -F force=true',
            'gh pr "$(echo merge)" 3 && gh pr merge 3']

    # Commands that run: other branches, and text that only mentions a merge or a push.
    ALLOW = ['gh api -X PUT repos/o/r/contents/f -f content="$(printf x | base64)" -f branch=feat/x',
             'echo "gh pr merge $(date)"', 'git commit -m "$(cat msg.txt)" -- a.py',
             'git push -u origin feature/x', 'git push origin --delete old-branch', 'git branch -D stale',
             'git worktree remove --force ../wt', 'git worktree prune', 'rm -rf ../old-worktree',
             'gh pr create --title "merge fix" --body x', 'gh pr create --body "then git push origin main (later)"',
             'gh pr view 3 --json mergeable', 'gh pr list', 'gh pr list --search merge', 'echo gh pr merge 3',
             'echo git push origin main', 'grep -rn "git push origin main" docs', 'git merge main',
             'git push origin feature:feature', 'git push --tags', 'npm run build', 'git reset --hard HEAD~1',
             'gh api repos/o/r/git/refs/heads/main', 'gh api -X PATCH repos/o/r/git/refs/heads/feature -f sha=abc',
             'gh api -X DELETE repos/o/r/git/refs/heads/old', 'gh api -X PUT repos/o/r/contents/x -f branch=feature',
             'echo "a (b) {c} & d"', 'git log --oneline -3', 'git push origin main-backup',
             'gh api -X DELETE repos/o/r/git/refs/heads/main-old', 'gh api -X PATCH repos/o/r/git/refs/heads/main.bak -f sha=a',
             'gh api repos/o/r/git/refs -f ref=refs/heads/main-v2 -f sha=a', 'gh api -X PUT repos/o/r/contents/x -f branch=main-docs',
             'git push origin feature>/dev/null',
             'gh pr create --title x --body "$(cat <<\'EOF\'\n## Summary\nOwner: merge with `gh pr merge 12 --squash`\nEOF\n)"',
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
                out = self.bash(command)
                self.assertIsNotNone(out, command)
                self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_everything_else_runs(self):
        for command in self.ALLOW:
            with self.subTest(command):
                self.assertIsNone(self.bash(command), command)

    def test_the_branches_come_from_the_repository(self):
        git(self.repo, 'switch', '-q', '-c', 'feature')  # current branch: a bare push, a push option and `@` target feature
        for command in ('git push', 'git push -o ci.skip origin', 'git push origin @'):
            self.assertIsNone(self.bash(command), command)
        self.assertIsNotNone(self.bash('git push origin HEAD:main'))
        git(self.repo, 'branch', '-q', '-D', 'main')  # no local default branch: --all runs, --mirror still does not
        self.assertIsNone(self.bash('git push --all origin'))
        self.assertIsNotNone(self.bash('git push --mirror origin'))
        git(self.repo, 'branch', 'trunk')  # the default branch is the target of origin/HEAD
        git(self.repo, 'update-ref', 'refs/remotes/origin/trunk', 'HEAD')
        git(self.repo, 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/trunk')
        self.assertIsNotNone(self.bash('git push origin trunk'))
        self.assertIsNone(self.bash('git push origin main'))

    def test_git_dash_c_is_followed_to_that_checkout(self):
        wt = Path(self.tmp.name) / 'wt'
        git(self.repo, 'worktree', 'add', '-q', '-b', 'feature', str(wt))
        self.assertIsNotNone(self.bash(f'git -C {self.repo} push', cwd=str(wt)))
        self.assertIsNone(self.bash(f'git -C {wt} push -u origin HEAD'))
        self.assertIsNone(self.bash(f'git -C {wt} push'))

    def test_a_missing_cwd_still_denies_and_other_tools_and_odd_inputs_are_not_checked(self):
        out = self.bash('git push origin main', cwd=str(self.repo / 'gone'))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'Edit', 'tool_input': {'command': 'gh pr merge 1'}}))
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'Bash', 'tool_input': {'command': 123}}))
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'Bash', 'tool_input': {}, 'cwd': 5}))

    def test_powershell_and_an_mcp_merge_tool_are_guarded_too(self):
        out = self.hook('pre-tool-use', {'tool_name': 'PowerShell', 'tool_input': {'command': 'gh pr merge 1'}})
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        out = self.hook('pre-tool-use', {'tool_name': 'mcp__github__merge_pull_request', 'tool_input': {}})
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIsNone(self.hook('pre-tool-use', {'tool_name': 'mcp__github__get_pull_request', 'tool_input': {}}))



class FableTest(RepoCase):
    """One Fable critic at a time, and the model matrix during an Orchestra run."""
    CRITIC = 'orchestra:critic-fable'
    # (script outside a run, words of the deny reason or None when allowed): where a workflow may name the critic
    CRITIC_SCRIPTS = [
        ("const r = await agent('x', {agentType: 'orchestra:critic-fable'})", None),
        ("await agent('a', {agentType: 'orchestra:critic-fable'})\nawait agent('b', {agentType: 'orchestra:critic-fable'})", ('once', 'critic-fable')),
        ("await agent('a', {agentType: 'orchestra:critic-fable'})\nawait agent('b', {agentType: 'critic-fable'})", ('once',)),
        ("await Promise.all(units.map(u => agent(u, {agentType: 'orchestra:critic-fable'})))", ('loop',)),
        ("for (const u of units) {\n  await agent(u, {agentType: 'orchestra:critic-fable'})\n}", ('loop',)),
        ("for (const x of xs) await agent(x, {agentType:'orchestra:critic-fable'})", ('loop',)),
        ("while (i++ < 5) await agent(x, {agentType:'orchestra:critic-fable'})", ('loop',)),
        ("for (const x of xs)\n  agent(x, {agentType:'orchestra:critic-fable'})", ('loop',)),
        ("await parallel([\n () => agent('a', {\n agentType: 'critic-fable' }) ])", ('loop',)),
        ("const c = (x) => agent(x, {agentType: 'orchestra:critic-fable'})\nawait Promise.all([c(a), c(b)])", ('function',)),
        ("async function judge(x) {\n  return agent(x, {agentType: 'orchestra:critic-fable'})\n}\nawait judge(a)", ('function',)),
        ("const judge = async (x) => { return await agent(x, {agentType: 'critic-fable'}) }", ('function',)),
        ("const o = {agentType: 'orchestra:critic-fable'}\nawait Promise.all([agent(a, o), agent(b, o)])", ('outside',)),
        ("const o = {agentType: 'orchestra:critic-fable'}\nconst c = x => agent(x, o)\nawait Promise.all([c(a), c(b)])", ('outside',)),
        # a brief or a comment that mentions a loop or the critic is text, not code
        ("await agent('Judge the plan for (A1..A6) with a for (x) review', {agentType: 'orchestra:critic-fable'})", None),
        ("await agent('Say critic-fable once, map( and agent( are text', {agentType: 'orchestra:critic-fable'})", None),
        ("// agentType: 'orchestra:critic-fable' was dropped\n/* for (x of y) agent(a, {agentType: 'critic-fable'}) */\n"
         "await agent(`one for (x) and critic-fable`, {agentType: 'orchestra:critic-fable'})", None),
        # a Fable model override in a workflow agent() is the Agent tool's rule too
        ("await Promise.all(xs.map(x => agent(x, {agentType:'orchestra:builder', model:'fable'})))", ('Fable',)),
        ("await agent(p, {agentType:'orchestra:critic', model:'claude-fable-5-2'})\n"
         "await agent(q, {agentType:'orchestra:critic', model:\"Claude-Fable-5-2\"})", ('Fable',)),
        ("await Promise.all(xs.map(x => agent(x, {agentType:'orchestra:builder', \"model\": 'fable'})))", ('Fable',)),
        ("await Promise.all(xs.map(x => agent(x, {agentType:'orchestra:builder', 'model': 'claude-fable-5-2'})))", ('Fable',)),
        ("await agent(p, {agentType:'orchestra:builder', model:'sonnet'})", None),
        # one critic call written on a line that also holds a spread map is still one call
        ("await Promise.all([agent(brief,{agentType:'orchestra:critic-fable'}), ...briefs.map(b => agent(b, {agentType:'orchestra:reviewer'}))])", None),
        # a fallback to the plain critic is a different type
        ("try {\n  await agent('Judge', {agentType: 'orchestra:critic-fable'})\n} catch (e) {\n"
         "  await agent('Judge again; critic-fable was unavailable', {agentType: 'orchestra:critic'})\n}", None),
    ]
    # (script inside a run, words of the deny reason or None): every workflow agent names a type
    RUN_SCRIPTS = [
        ("await agent('x')", ('agentType', 'main session')),
        ("await agent('x', {agentType: 'orchestra:builder'})", None),
        ("await agent('x', {agentType: 'orchestra:builder'}); await agent('y')", ('agentType',)),
        ("const o = {agentType: 'orchestra:reviewer'}\nawait agent(p1, o)\nawait agent(p2, o)", None),
        ("const o = {}\nawait agent(p1, o)", ('agentType',)),
        ("await agent(p1, {model: 'sonnet'})", ('agentType',)),
        ("await agent('Call agent( on it', {agentType: 'orchestra:builder'})", None),
    ]

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

    def ledger(self, text='- [>] A1: open\n'):
        lean.state_dir(self.cwd, 'sess', create=True)
        lean.ledger(self.cwd, 'sess').write_text(text)

    def unlock(self):
        (lean.state_dir(self.cwd, 'sess') / 'fable.lock').unlink(missing_ok=True)

    def denied(self, out, *words):
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        for w in words:
            self.assertIn(w, out['hookSpecificOutput']['permissionDecisionReason'])

    def expect(self, out, words):
        if words is None:
            self.assertIsNone(out)
        else:
            self.denied(out, *words)

    def test_one_critic_call_is_allowed_by_either_tool_name_and_either_type_name(self):
        for tool, name in (('Agent', self.CRITIC), ('Task', 'critic-fable')):
            self.assertIsNone(self.call({'subagent_type': name}, tool))
            self.unlock()

    def test_a_second_critic_is_denied_only_while_one_runs(self):
        for type_, stop, age, blocks in (
                (self.CRITIC, 'tool_use', 0, True), (self.CRITIC, 'end_turn', 0, False),
                (self.CRITIC, 'tool_use', lean.LIVE_WORKER_SECONDS + 60, False), ('orchestra:builder', 'tool_use', 0, False)):
            with self.subTest(type_=type_, stop=stop, age=age):
                shutil.rmtree(self.transcript.with_suffix(''), ignore_errors=True)
                worker(self.transcript, type_, stop, age)
                self.expect(self.agent(self.CRITIC), ('one Fable critic',) if blocks else None)
                self.unlock()

    def test_a_lock_blocks_a_second_call_until_it_is_stale_or_its_critic_finished(self):
        self.assertIsNone(self.agent(self.CRITIC))
        self.denied(self.agent(self.CRITIC), 'one Fable critic')
        lock = lean.state_dir(self.cwd, 'sess') / 'fable.lock'
        old = time.time() - 31 * 60
        os.utime(lock, (old, old))
        self.assertIsNone(self.agent(self.CRITIC))
        worker(self.transcript, self.CRITIC, 'end_turn')
        self.assertIsNone(self.agent(self.CRITIC))

    def test_a_fable_model_override_on_another_type_is_denied(self):
        self.denied(self.agent('orchestra:builder', model='claude-fable-5-2'), 'critic-fable')
        self.denied(self.agent(None, model='Fable'), 'critic-fable')
        self.assertIsNone(self.agent('orchestra:builder', model='sonnet'))

    def test_a_critic_outside_a_git_repository_writes_no_lock_into_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.hook('pre-tool-use', {'tool_name': 'Agent', 'tool_input': {'subagent_type': self.CRITIC},
                                             'cwd': d, 'session_id': 'sess', 'transcript_path': str(self.transcript)})
            self.assertIsNone(out)
            self.assertEqual(os.listdir(d), [])

    def test_where_a_workflow_may_name_the_critic(self):
        for text, words in self.CRITIC_SCRIPTS:
            with self.subTest(text):
                self.unlock()
                self.expect(self.script(text), words)

    def test_a_workflow_script_file_is_read_and_a_running_critic_denies(self):
        f = Path(self.tmp.name) / 'wf.js'
        f.write_text("agent('a', {agentType: 'critic-fable'}); agent('b', {agentType: 'critic-fable'})")
        self.denied(self.call({'scriptPath': str(f)}, 'Workflow'), 'once')
        f.write_text("agent('a', {agentType: 'critic-fable'})")
        worker(self.transcript, self.CRITIC)
        self.denied(self.call({'scriptPath': str(f)}, 'Workflow'), 'one Fable critic')

    def test_the_matrix_is_silent_outside_a_run(self):
        self.assertIsNone(self.agent())
        self.assertIsNone(self.script("agent('x')"))
        self.ledger('- [x] A1: done\n')
        self.assertIsNone(self.agent('general-purpose'))

    def test_in_a_run_an_agent_names_an_orchestra_type_or_an_explicit_non_fable_model(self):
        self.ledger()
        for t in (None, 'general-purpose', 'claude', 'fork'):
            self.denied(self.agent(t), 'orchestra:', 'main session')
        for t in ('Explore', 'Plan', 'orchestra:builder', 'other-plugin:thing'):
            self.assertIsNone(self.agent(t))
        self.assertIsNone(self.agent(None, model='opus'))
        self.assertIsNone(self.agent('general-purpose', model='sonnet'))

    def test_in_a_run_every_workflow_agent_names_a_type(self):
        self.ledger()
        for text, words in self.RUN_SCRIPTS:
            with self.subTest(text):
                self.expect(self.script(text), words)

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



class PushGateTest(RepoCase):
    """During a run a push of a branch needs the test gate to hold."""
    PUSHES = ['git push', 'git push origin', 'git push -u origin feat/x', 'git -C {repo} push origin feat/x',
              'sudo git push -u origin feat/x', 'bash -c "git push origin feat/x"', 'git push origin HEAD']

    def setUp(self):
        super().setUp()
        git(self.repo, 'switch', '-q', '-c', 'feat/x')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'work')  # a branch with no commits beyond main has nothing to gate
        git(self.repo, 'tag', 'v1.0')

    def ledger(self):
        lean.state_dir(self.cwd, 'sess', create=True)
        lean.ledger(self.cwd, 'sess').write_text('- [>] A1: open\n')

    def push(self, command='git push -u origin feat/x'):
        return self.bash(command.format(repo=self.repo), session_id='sess')

    def hold_gate(self):
        import gate
        head = git(self.repo, 'rev-parse', 'HEAD')  # a skip counts only for a head on the branch, not on main
        lean.write_json(gate.file(self.cwd), {'feat/x': {'skips': {k: {'reason': 'no runner', 'head': head} for k in ('unit', 'e2e')}}})

    def test_a_push_is_denied_in_a_run_while_the_gate_lacks_lines(self):
        self.ledger()
        for command in self.PUSHES:
            with self.subTest(command):
                out = self.push(command)
                self.assertIsNotNone(out, command)
                reason = out['hookSpecificOutput']['permissionDecisionReason']
                self.assertIn('no full unit run recorded', reason)
                self.assertIn('no green e2e run', reason)
                self.assertIn('gate skip', reason)

    def test_a_push_runs_outside_a_run_with_the_switch_or_with_a_holding_gate(self):
        self.assertIsNone(self.push())
        self.ledger()
        os.environ['ORCHESTRA_GATE'] = 'off'
        self.assertIsNone(self.push())
        del os.environ['ORCHESTRA_GATE']
        self.hold_gate()
        self.assertIsNone(self.push())

    def test_a_branch_with_no_commits_beyond_main_needs_no_gate(self):
        self.ledger()
        git(self.repo, 'switch', '-q', '-c', 'feat/empty', 'main')
        self.assertIsNone(self.push('git push -u origin feat/empty'))

    def test_an_active_goal_counts_as_a_run(self):
        lean.state_dir(self.cwd, 'sess', create=True)
        lean.write_json(lean.goal_file(self.cwd, 'sess'), {'state': 'active'})
        self.assertIsNotNone(self.push())

    def test_a_delete_or_a_tags_only_push_needs_no_gate(self):
        self.ledger()
        for command in ('git push origin --delete old', 'git push origin :old', 'git push --tags', 'git push origin --tags',
                        'git push origin refs/tags/v1',
                        'git push origin v1.0', 'git push origin +v1.0'):
            with self.subTest(command):
                self.assertIsNone(self.push(command), command)
        self.assertIsNotNone(self.push('git push origin v2.0'))  # no such tag: a branch to create

    def test_the_default_branch_deny_stays_first(self):
        self.ledger()
        out = self.push('git push origin main')
        self.assertIn('only the owner', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_a_gate_that_cannot_be_read_lets_the_push_run(self):
        self.ledger()
        import gate
        with mock.patch.object(gate, 'missing', side_effect=OSError):
            self.assertIsNone(self.push())


if __name__ == '__main__':
    unittest.main()
