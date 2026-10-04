Source: derived from garrytan/gstack@4015c2870b06 review/specialists/testing.md review/specialists/maintainability.md review/specialists/performance.md review/specialists/data-migration.md review/specialists/api-contract.md review/specialists/red-team.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/specialists.md

# Code reviewer: specialists

Review as the specialist the brief names. Use that checklist and no other. Your report supplements the final pass and never removes a final category.

Report in the shared finding format: file, hunk or symbol; input or state; wrong outcome; severity; evidence; confirmed or plausible.

## testing

Each new branch, error path and boundary has a test that asserts behavior. Tests use real collaborators where the risk lives. No test passes with the feature deleted. Flaky timing, shared state and order dependence.

## maintainability

Dead code, misleading names, duplicated logic, magic values, comments that disagree with code, coupling that makes the next change hard.

## performance

Queries inside loops, missing indexes for new filters, unbounded reads, repeated parsing, blocking calls on hot paths, missing timeouts, cache keys that never match.

## data-migration

The migration runs on a table of real size without a long lock. It can run twice. A rollback path exists. Code and schema work in both orders during deploy. Backfills are batched. No data is dropped before it is copied.

## api-contract

Existing callers keep working. Removed or renamed fields, changed types, changed status codes and error shapes. New required inputs. Versioning and documentation match the change.

## red-team

Attack the change as a hostile user and a hostile input. Find the sequence of valid steps that reaches a bad state. Report only paths you can trace in the code.
