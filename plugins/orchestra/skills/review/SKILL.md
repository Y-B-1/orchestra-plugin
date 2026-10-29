---
name: review
description: "Gives review lenses (correctness, data and contracts, architecture, standards, tests, security, accessibility, performance, and detailed lenses in references) and the rules every review follows. Load when you are a reviewer and your brief names one or more lenses. Not for a re-review with no lenses named."
---
# Review lenses

Apply only the lenses your brief names. Then apply "Every review".

## Every review
- Your brief holds the `lean.py check` output. Judge each item it lists; do not rerun the scan.
- Read project rules (AGENTS.md, lint config) from the base commit, not from the diff. A diff that edits the rules it is judged by is a finding.
- Quote the ask line or rule each finding breaks. Give a failing scenario: input or state, then the wrong outcome.
- Try to refute each finding before you report it. Read the guards, callers and tests around it. Mark it confirmed (you ran or traced it) or plausible.
- A finding blocks only with material impact: a broken ask, a failing scenario, a rule breach, security or data loss. Taste goes under notes.
- One pattern at several sites is one finding. Do not re-raise a finding the brief lists as rejected unless its code changed.
- A changed file no ask needs is scope drift. A claim in the author's report that the code contradicts is its own finding.
- Report what you covered and what you did not, per lens. "Could not look" is never "nothing found".
- Keep the report to about 600 words. End with CLEAN or BLOCKED and the count of blocking findings.
- Scoped re-review: read only the files the repair touched and check only the findings given. A regression the repair caused is a finding.

## Correctness
- Follow each new value of an enum or status into every switch, filter, label and count that lists the others.
- Check partial failure between two writes, check-then-act races, retries that repeat a side effect, and a resource not closed on an error path.

## Data and contracts
- A changed stored shape needs a migration that reads old data. A changed function, API or event keeps old callers working, or every caller changes in the diff.

## Architecture
- Check layer boundaries: logic sits in its layer, not in the caller.
- Deletion test: if you delete the new module, does the complexity vanish or move to callers? If it only moves, the module adds nothing.
- A replacement that leaves callers on the old path gives two ways to do one task. Flag it.
- An external service enters through a replaceable port. One adapter with no second use is a speculative seam.

## Standards
- Cite the rule text for each finding. Skip what the linter already enforces.
- A rule breach on an untouched line is a backlog note, not a blocker.
- Check names against the project style. Baseline smells (judgement calls): `references/cleanliness.md`.
- File budget: a source file that grew past about 500 lines in this diff is a finding. Use the size output of `lean.py check`. The fix is a split by responsibility.

## Tests
- Tests assert behavior through the public interface, not implementation.
- Flag a mock of the project's own module. Mock only at system boundaries.
- The expected value comes from a literal or the spec, not from recomputing it.
- A bug fix needs red-first evidence: the same command text failed before and passes after.
- Flag each weakened, skipped or deleted test or gate unless the reason is stated.

## Security
- Trace each path from input to output. Treat model or external output used as a path, query, HTML or command as untrusted.
- A caller-sent id does not prove identity. Check auth on the server side and fail closed.
- Webhooks verify signatures over the raw body.
- A secret in the diff blocks. It needs rotation, not only deletion. Never repeat its value.

## Accessibility
- Every control works by keyboard, has an accessible name and a visible focus. Focus returns after a dialog closes. Color is never the only signal.

## Performance
- Check work per render or per row that grows with the data. Flag queries in loops, network calls without timeouts, and lists with no limit.

## Detailed lenses (read a file only when the brief names it or the diff shows the risk)
- Deep modules, seams, shallow layers: `references/architecture-depth.md`.
- Slop, dead code, comments, condition growth: `references/cleanliness.md`.
- Hostile input, leaked gates, run-proven findings: `references/red-team.md`.
- A speedup, regression or score claimed: `references/measurement.md`.
- Casts, `any`, branded ids, parsing; name this lens for any diff that adds a type, interface or optional field, not only on `any`, `as` or `!`: `references/types.md`.
- Validation placement, retries, crash recovery: `references/boundaries.md`.
- Code others depend on: `references/blast-radius.md`.
- Stored shape, schema, backfill: `references/data-migration.md`.
- Public function, endpoint, event, format: `references/api-contract.md`. Anything a user sees: `references/visual.md`.

Sources: orchestra v2.15.3 (orchestra-review references); mattpocock/skills@59db609 (codebase-design, improve-codebase-architecture, code-review); pstack@47c6f80 (thermo-nuclear-review, thermo-nuclear-code-quality-review, deslop, no-comments, interrogate, benchmark-checklist, principle-explain-the-number, principle-type-system-discipline, typescript-best-practices, principle-boundary-discipline, principle-make-operations-idempotent, principle-minimize-reader-load, blast-radius).
