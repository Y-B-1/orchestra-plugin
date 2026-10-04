Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/productivity/handoff/SKILL.md (MIT); garrytan/gstack@4015c2870b06 context-save/SKILL.md context-restore/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/handoff.md

# Progress ledger, resume and handoff

## Ledger

`<state>/progress.md` is the run ledger. It survives compaction where conversation memory does not. The first line names the plan or run it belongs to; a ledger naming another plan is left alone. Append one line per event with six fields: time, card, action, artifact SHA, round and decision. The action is dispatched, reported, accepted, repair round or ruling. The decision records what was decided, why, and the cost if it is wrong. Never rewrite earlier lines.

## Resume

Check in this order:

1. The ledger. After compaction it outranks recollection.
2. `python3 <plugin>/scripts/orchestra.py status`.
3. Live worker state. Check liveness: a live process, and the transcript's last modification time. A journal line records what started, not what still runs.
4. Artifacts: `git log`, `git status`, and each report against its logs.
5. `python3 <plugin>/scripts/orchestra.py start`: a new lease requeues running cards.
6. Re-dispatch by ledger line: a card with a completion line is never dispatched again. A card whose last line is a repair round resumes at the next round.

Re-inspect the artifact before accepting a report from before the interruption.

## Handoff

Write a handoff for a fresh agent into the temporary directory, outside the workspace. Use named sections:

- Goal and current lane
- Decisions made, each with its reason
- Remaining work, in dependency order
- Open risks and unavailable checks

Point to specs, plans, issues, commits and diffs by path or URL instead of copying them. Tailor the document to what the next session will do. Redact credentials, tokens and personal data. End with the ledger path and the artifact identity.
