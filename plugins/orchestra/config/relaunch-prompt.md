# Orchestra relaunch pass

You are one fresh pass of a run that `orchestra.py relaunch` repeats until it stops. Earlier passes and the next one share no memory with you; the run state on disk is the only continuity.

1. Read the `orchestra` skill and follow it. The SessionStart context names this plugin's `scripts/orchestra.py` and your harness session id.
2. Run `orchestra.py start --harness-session <id from SessionStart>`. Keep the lease it prints.
3. Read the run's `progress.md` (named in the SessionStart context) and run `orchestra.py status`. They say what earlier passes did and what is left.
4. Dispatch every ready card, review and accept finished work, and keep the board moving. Park a card with `orchestra.py park` the moment it reaches an approval boundary; never cross one.
5. Never end your turn to wait for anything. Waiting passes burn the run: do the next ready card, or park, or finish.
6. When your context nears its ceiling, record state first (reports, reviews, `progress.md` notes), then end the pass. The harness starts a fresh one.

Rules for this headless pass:

- Use foreground (blocking) Agent calls only. A background agent is killed when the pass exits.
- Never run background Bash, and never start a background process: `claude -p` kills it at exit.
- Workflow is allowed in the foreground; wait for its result before you continue.
- Workers do not delegate, and you never release, push or delete outside the approval boundaries of the ledger.
