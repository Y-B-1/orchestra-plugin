# Git guardrails

Only when the owner asks. This is a hook in the owner's project, separate from Orchestra's own guard, which stays merge-only.

1. Ask the owner for the scope: this project or all projects.
2. Install a PreToolUse Bash hook in that scope's settings that exits 2 when the command contains `git push`, `reset --hard`, `clean -f`, `branch -D`, `checkout .` or `restore .`.
3. Test it by piping `{"tool_input":{"command":"git push origin main"}}` to the hook and expect exit 2. Pipe a harmless command such as `git status` and expect exit 0.
