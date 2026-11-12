# Git guardrails

Only when the owner asks. This is a hook in the owner's project, separate from Orchestra's own guard, which stays merge-only. Orchestra installs this only when the owner asks, and never in its own plugin.

The hook must never block a plain push of a feature branch or opening a PR, because Orchestra's finish step and the /goal Stop hook push the branch. It blocks only destructive forms: a force push (`--force`, `--force-with-lease`, `-f` alone or in a cluster like `-fu`, `+refspec`), a push to the default branch (named, or a bare push while on it), `reset --hard`, `clean -f`, `branch -D`, `checkout .` and `restore .` (unstaging with `restore --staged .` stays allowed). It reads the command by position, so words inside a commit message never match. A rebased branch that needs a force push is the owner's step.

1. Ask the owner for the scope: this project or all projects.
2. Copy `references/git-guardrails.py` (beside this file) to `.claude/hooks/git-guardrails.py` (or `~/.claude/hooks/git-guardrails.py`) and `chmod +x` it. Replace `main` and `master` in `DEFAULT` if the default branch has another name.
3. Install it as a PreToolUse Bash hook in that scope's settings. If the settings file exists, merge the hook into its existing `hooks.PreToolUse` array and never overwrite other settings.
4. Test it by piping `{"tool_input":{"command":"..."}}` to the script on a feature branch. Expect exit 2 for `git push --force origin feature-x`, `git push -fu origin feature-x`, `git push origin HEAD:main`, `git clean --force -d`, and `cd repo` then `git reset --hard` on two lines. Expect exit 0 for `git push origin feature-x`, `git push origin feature/main`, `gh pr create`, `git stash push -m wip` and `git commit -m "never push to main"`.
