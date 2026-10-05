Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md skills/executing-plans/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/review-army.md bin/gstack-diff-scope (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/final-review.md

# Final review

Run the final review on the integrated, frozen candidate. Any later edit voids it.

## Three lenses

1. The operator gates the integrated candidate. Reviewers cite that receipt and run targeted probes, never the full suites; any later change needs a re-gate.
2. Dispatch three code-reviewer cards in parallel, each with a `Lens:` line and covering every task, held ones included: correctness (requirements, correctness, tests, architecture), security, and standards (standards, cleanup, with the cleanliness checklist). The size gate below decides only whether specialists run. What each lens checks lives in the orchestra-review skill.
3. Each brief carries the held log, the gate receipts and `## Known findings`. A lens attributes every blocking finding in `task_findings` to the chain tip whose change introduced it, and either blocks or clears every held tip (`cleared`, with a reason).

A defect no card's change introduced is out of scope. So is a defect from a card that is not a builder (operator, designer-planner, an inline edit): it has no chain tip, so the lens raises it in `out_of_scope` naming that card. Triage each item with `orchestra.py finding add --kind out_of_scope --disposition inline|card|brief`. A non-builder cause goes to inline or card, never brief alone. Out-of-scope items never change a verdict, and completion needs each triaged.

## Final repair rounds

1. Accept first: the lens cards, investigator cards and every acceptable chain. A held tip that every lens cleared accepts with no repair.
2. Add one Opus repair card per chain with a current attributed finding, held or not, targeting the chain tip and storing `final_round` and `final_findings`. Add them together and dispatch through the Agent tool (references/parallel.md).
3. When the repairs report, re-run each lens that failed over all tasks, limited to the still-failing items and the round's repair diff. Accept passing chains tip-first.
4. A chain still failing gets another round, with no count limit. If a finding repeats (same fingerprint, or the same chain blocked again by the same lens), investigator-code re-diagnoses a repeated finding before the next repair, and that brief carries the diagnosis and the approach to avoid. The run deadline is the only outer limit.
5. When every re-check is clean, the operator re-gates. Each lens whose last clean receipt went stale records one closing confirmation over the cumulative repair diff. A blocking finding there starts another round.

Notes never start a round. Within each round (lens round, re-check, closing confirmations), add every card of the round, then let all report, then record: a receipt recorded before a later card of its round is added is stale for coverage.

## Specialists

Add specialist reviewers only when `git diff --shortstat BASE..HEAD` reports more than 50 changed lines and the changed paths match the specialist's surface. Build the changed set from committed changes, the working tree and untracked files. Distinguish "could not look" (an unresolvable base, a failed command) from "nothing matched". Never read a failure to look as a clean match; stop and report it.

Brief a specialist as a code-reviewer card with `Lens: specialist:<name>`, where `<name>` is a section heading of `skills/orchestra-review/references/specialists.md` under the plugin root (frontend, visual, testing and the rest). The lens line only names the checklist; it never decides whether the card runs or what the verdict is.

Merge and dedupe findings across lenses and specialists before routing.
