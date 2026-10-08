Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md skills/executing-plans/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/review-army.md bin/gstack-diff-scope (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/final-review.md

# Pre-PR review

Run the pre-PR review once, on the integrated, frozen PR candidate. It is the only independent code review. Any later edit voids it.

## Lenses

1. The operator gates the gap first: the derived impact set and e2e. Reviewers cite that receipt and run targeted probes, never the full suites; any later change needs a re-gate.
2. Derive the lenses from the diff. `status` shows `required_lenses`. Dispatch one code-reviewer card per lens in parallel, each with a `Lens:` line and covering every task, held ones included:
   - correctness, always (requirements, correctness, tests, architecture);
   - security, when a changed file matches a glob in policy `sensitive_paths`;
   - standards (standards, cleanup, with the cleanliness checklist), when the run's diff exceeds policy `standards_min_lines` changed lines.

   The changed set is the diff from the run's base commit to the working tree, untracked files included. A policy `required_review_categories` overrides the derived set. What each lens checks lives in the orchestra-review skill.
3. Each brief carries the held log, the gate receipts and `## Known findings`. A lens attributes every blocking finding in `task_findings` to the chain tip whose change introduced it, and either blocks or clears every held tip (`cleared`, with a reason).

A defect no card's change introduced is out of scope. So is a defect from a card that is not a builder (operator, designer-planner, an inline edit): it has no chain tip, so the lens raises it in `out_of_scope` naming that card. Triage each item with `orchestra.py finding add --kind out_of_scope --disposition inline|card|brief`. A non-builder cause goes to inline or card, never brief alone. Out-of-scope items never change a verdict, and completion needs each triaged.

## After the review

Accept first: the lens cards, investigator cards and every acceptable chain. A held tip that every lens cleared accepts with no repair.

Add one Opus repair card per chain with a current attributed finding, then one fix re-review of the fix diff (references/repair-rounds.md). After a CLEAN fix re-review, the pre-PR review stays current when every file changed since it belongs to a repair the fix re-review covered. Otherwise re-gate and review again. A BLOCKED chain is held for the owner.

Notes never start a repair. Add every lens card, let all report, then record: a receipt recorded before a later card of its set is added is stale for coverage.

## Specialists

Add specialist reviewers only when `git diff --shortstat BASE..HEAD` reports more than 50 changed lines and the changed paths match the specialist's surface. Build the changed set from committed changes, the working tree and untracked files. Distinguish "could not look" (an unresolvable base, a failed command) from "nothing matched". Never read a failure to look as a clean match; stop and report it.

Brief a specialist as a code-reviewer card with `Lens: specialist:<name>`, where `<name>` is a section heading of `skills/orchestra-review/references/specialists.md` under the plugin root (frontend, visual, testing and the rest). The lens line only names the checklist; it never decides whether the card runs or what the verdict is.

Merge and dedupe findings across lenses and specialists before routing.
