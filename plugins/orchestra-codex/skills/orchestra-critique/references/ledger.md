Source: derived from obra/superpowers@8ca22dba9a94 skills/requesting-code-review/code-reviewer.md (MIT); garrytan/gstack@4015c2870b06 review/sections/plan-completion.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-build/references/claims-check.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-critique/references/ledger.md

# Critic: ledger mode

Audit what the run records against what happened. This axis asks only whether the record is true; whether the code is right belongs to the other axes.

## Order

Collect the evidence first: artifact commits, gate logs, review verdicts, the engine status and the repository state. Read the progress ledger and the reports last.

## Claims to test

Test these claims:

- Completion: the card is closed. Find the artifact, its full commit and the passing check behind it.
- Approvals: the approver is a named reviewer, independent of the builder, and the approval names the same artifact.
- Gate artifacts: each log exists, carries the exact command and exit code, and ran on the claimed commit and tree state.
- Review independence: no reviewer reviewed work it built, and no evidence from one artifact stands in for another.
- Authorization: a release, merge or push has an explicit assignment or user approval that predates it.
- Run history: round numbers, parked cards and decisions in the ledger match the review and report history.

## Defects to look for

- A stale fingerprint: the evidence names a commit or tree that is not the current candidate.
- An omitted failure: a red run, a blocked review or a retry the ledger leaves out.
- An altered log: a truncated or reordered file, a missing exit code, a timestamp outside the run.
- An unsupported release claim: shipped, merged or released without the required evidence.

## Report

Classify each claim with the core classes. A claim with no log is UNVERIFIABLE, never DONE. For each finding, give the ledger line, the contradicting artifact and the invalidated claim. State which later edits void which evidence.
