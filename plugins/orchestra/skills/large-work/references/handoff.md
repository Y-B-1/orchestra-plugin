# Handoff and resume

## Write a handoff
Write it for a fresh agent into `$TMPDIR`, else `/tmp` (`%TEMP%` on Windows), outside the workspace. Named sections:
- Goal and current state
- Decisions made, each with its reason
- Remaining work, in dependency order
- Open risks and checks that could not run
- Suggested skills the next agent should load
- Progress ledger path and the artifact identity (branch, commit)

Rules:
- Point to specs, plans, issues, commits and diffs by path or URL. Never copy them.
- Write each claim about code as of a commit ("as of <sha>"), never "currently". Mark an outdated claim superseded; do not edit it.
- Redact credentials, tokens and personal data. The summary may become another agent's prompt.
- If the owner gave a focus for the next session, tailor the document to it.
- To start the next agent at once, run `claude --bg --name "<descriptive name>" -- "$(cat <file>)"`. Pass the file so the shell does not expand the text. It starts in the current directory and returns at once.

## Progress ledger
Keep an append-only ledger in the run's state folder. First line names the run. One line per event: time, unit, action (dispatched, reported, accepted, repair, hold, pr), artifact SHA, decision. It outlasts compaction; recollection does not.

## Resume
Check in this order:
1. The ledger. After compaction it outranks recollection.
2. The newest run brief or handoff file.
3. Live worker state: a live process first, then the transcript's last modification time. A quiet transcript alone is not a stopped worker.
4. Artifacts: `git log`, `git status`, each report against its logs.
5. Re-dispatch by ledger line. A unit with a completion line is never dispatched again. A unit whose last line is a repair resumes at the fix re-review. A held unit waits for the owner.

Re-inspect the artifact before accepting a report from before the interruption.
