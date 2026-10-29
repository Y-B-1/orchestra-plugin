# Red team lens

Attack the change as a hostile user and a hostile input. Report findings only. A finding blocks only when you traced or ran it.

## Frame
- State the intent in two sentences from the ask, the commits and the PR text. Judge only added or changed code.
- If the brief offers a run command, a finding needs a run: a failing test, a repro, or command output that shows the wrong result. Quote the command and its output. Without a run, mark it plausible.

## Attack list
- A sequence of valid steps that reaches a bad state: skipped step, repeated step, reordered step, two actors at once.
- Input at the edges: empty, huge, duplicate, wrong type, hostile string in a path, query, header or command.
- Identity: a caller-sent id, a role check on the client only, a missing owner check on a read or delete.
- Gates: a feature flag, internal-only check or paywall that the change leaks past.
- Breakage elsewhere: callers, wire formats, jobs and scripts that read what the change alters (see `references/blast-radius.md`).
- Developer experience: renamed env vars, moved secrets or ports, a new required script. This breaks teammates even if prod works.
- Rollback: can the change be undone without data loss?

## Discipline
- Intended breakage the ask names, with a well-bounded scope, is not a finding. Flag it only if the author clearly missed an implication.
- Finish the research before you report. Do not write "fine if the backend handles it" when you can read the backend.
- Do not mis-rate severity. Over-reporting costs trust. A hypothetical with no path in the code is a note.
- Read the PR discussion and any review bot comments only after your own pass. Mark a finding that came from there.
- Merge findings that share a root cause. Drop what you could not support.

## Report
Per finding: title, command or code path, observed output or trace, the output the intent requires, severity, confirmed or plausible. End with what you attacked and could not break.
