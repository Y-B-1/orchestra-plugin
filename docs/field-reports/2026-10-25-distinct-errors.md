> **TEMPORARY. Delete the whole branch after the fixing session has read it. Do not merge, keep or link it.**

# Distinct Orchestra engine errors in the call log

Count, message. Card ids are replaced by CARD-n.

- 36 x `Self-review has a failing check or unmet criterion`
- 15 x `Invalid or interrupted coordinator lease. If this session lost its lease, take it back with `start --recover --harness-session ID` (the id is in the SessionStart context)`
- 15 x `Task is not ready or capacity is exhausted: its files or resources overlap a running, reported or repair card`
- 13 x `Invalid task size`
- 13 x `Task has no reported result`
- 13 x `Invalid assignment`
- 11 x `Supply --lease from start for coordinator actions`
- 11 x `Task is not parked`
- 10 x `No active run to recover; use start`
- 10 x `Task is not ready or capacity is exhausted`
- 10 x `Worktree cap: 3 builder cards are already running; wait for one to report`
- 9 x `Reported artifact is stale: the files in its scope changed after the report; re-report or send a repair card`
- 7 x `Start the whole wave: wave CARD-n CARD-n (or pass --serial REASON to start CARD-n alone)`
- 6 x `Builder brief needs the heading ## Keep`
- 6 x `Only a queued, running or reported card can be parked`
- 5 x `Only a queued or parked card can be cancelled; park a running or reported card first`
- 5 x `Ledger field deadline must be in the future`
- 5 x `[Errno 2] No such file or directory: '<PATH>'`
- 5 x `Start the whole wave: wave --inline CARD-n CARD-n (or pass --serial REASON to start CARD-n alone)`
- 4 x `Ledger uses the pre-2.11 Approval boundaries: copy the Merge, Push and Deletion lines from the template, then arm again`
- 4 x `Worker is already reserved`
- 4 x `Builder brief needs the heading ## Remove`
- 2 x `Tiny unit: the main session does this work; pass --helper REASON to dispatch a helper`
- 2 x `Task brief must carry the line Mode: frontend`
- 1 x `Task is not ready or capacity is exhausted: open dependencies: CARD-n`

# Shell-guard block messages

- 261 x `BLOCKED: ambiguous commit candidate: compound or future-mutating command`
- 62 x `BLOCKED: ambiguous commit candidate: executable shell expansion`
- 47 x `BLOCKED: ambiguous commit candidate: executable shell interpreter or dynamic command`
- 47 x `BLOCKED: ambiguous commit candidate: shell expansion or multiple commands`
- 20 x `BLOCKED: ambiguous commit candidate: unknown git command or alias`
- 19 x `BLOCKED: ambiguous commit candidate: unsupported executable shell form`
- 11 x `BLOCKED: gitleaks found secrets in commit candidate; remove secrets before committing`
- 4 x `BLOCKED: commit pathspec selects no tracked candidate`
- 4 x `BLOCKED: ambiguous commit candidate: pathspec file`
