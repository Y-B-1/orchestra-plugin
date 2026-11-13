# Handoff and resume

## Write a handoff
Before you create a notes or handoff file, look for the notes the repo already keeps (a docs folder, a memory file) and write there in its form.
Write it for a fresh agent to `<git common dir>/orchestra/handoffs/<branch>.md` (outside the working tree, durable). Use `$TMPDIR` only for the copy you pass to `claude --bg`. Named sections:
- Goal and current state
- Decisions made, each with its reason
- Remaining work, in dependency order
- Open risks and checks that could not run
- Suggested skills the next agent should load
- Progress ledger path and the artifact identity (branch, commit)

Rules:
- Point to specs, plans, issues, commits and diffs by path or URL. Never copy them.
- Write each claim about code as of a commit ("as of <sha>"), never "currently". Mark an outdated claim superseded; do not edit it.
- Quote an owner ruling in their own words with a pointer to where they said it. Mark what is your reading of it. A scoped instruction ("avoid that endpoint during this migration") stays scoped; never restate it as a permanent rule.
- Redact credentials, tokens and personal data. The summary may become another agent's prompt.
- If the owner gave a focus for the next session, tailor the document to it.
- To start the next agent at once, run `claude --bg --name "<descriptive name>" -- "$(cat <file>)"`. Pass the file so the shell does not expand the text. It starts in the current directory and returns at once.

## Progress ledger
Keep an append-only ledger beside it, `<git common dir>/orchestra/handoffs/<branch>.ledger`. First line names the run. One line per event: time, unit, action (dispatched, reported, accepted, repair, hold, pr), artifact SHA, decision. It outlasts compaction; recollection does not.

## Pause
On an explicit pause, in order:
1. Finish or back out the current step. Leave no half-applied edit.
2. Stop nested agents and workflows.
3. Push or open a PR only if one was already out. Take no other irreversible action.
4. Commit uncommitted edits as one `wip:` commit.
5. Write the handoff with a resume note: the next step, and where each kept artifact lives. Read it back to check it is complete.

## Resume
When a task continues earlier work, first rebuild its state from git, PRs and prior sessions. Tag each thread against `git` and `gh`: merged (#N), open PR (#N), in flight (branch), verified but uncommitted, reverted (#N), planned and not started. Carry forward each fix that shipped and was reverted, so the next attempt starts where the last one failed. Never turn "all" into "recent N".

Check in this order:
1. The ledger. After compaction it outranks recollection.
2. The handoff and ledger in `<git common dir>/orchestra/handoffs/`, else the newest run brief.
3. Live worker state: a live process first, then the transcript's last modification time. A quiet transcript alone is not a stopped worker.
4. Artifacts: `git log`, `git status`, each report against its logs.
5. Re-dispatch by ledger line. A unit with a completion line is never dispatched again. A unit whose last line is a repair resumes at the fix re-review. A held unit waits for the owner.

Before you report that something was never recorded, search every place the project's rules name (memory file, decision logs, ledgers, handoffs) and this project's own session transcripts.

Re-inspect the artifact before accepting a report from before the interruption.
