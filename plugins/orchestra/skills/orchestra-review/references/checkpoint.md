Source: derived from obra/superpowers@8ca22dba9a94 skills/requesting-code-review/code-reviewer.md skills/subagent-driven-development/task-reviewer-prompt.md skills/subagent-driven-development/re-review-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/code-review/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/SKILL.md review/sections/plan-completion.md (MIT); github/spec-kit@ae5ade7234be .github/skills/code-review/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/checkpoint.md

# Code reviewer: checkpoint mode

Review the ticket, review group or wave the brief names against its acceptance criteria. A group or wave lists every ticket it covers. Review each one, and raise nothing outside the reviewed change.

## Procedure

1. Read the acceptance criteria and the ownership list. Then read the diff.
2. Sort every gap into one of three classes. Missing: a criterion the code does not meet. Extra: behavior or files nobody asked for. Misunderstood: code that meets the wording and misses the intent.
3. Check the evidence. Each command the report cites must name a real command, its exit and a log path. Flag proof that is missing or that predates the last edit. The operator gate reruns the builder's acceptance suite and you never do. Cite its current receipt in `gate_receipts`; a receipt older than the last change is stale, so ask for a new one. You do run targeted probes, comparisons and counterexamples.
4. Sibling-owned paths stay untouched.
5. Check the tests:
   - The ticket has a test for what the code must do and a test for what it must prevent.
   - Test names and changed wording use the repository's own terms.
6. Confirm each `## Keep` item holds and each `## Remove` item is gone. A miss is a blocking finding for lost functionality.
7. A consequential foundation gets this review before dependent work starts. Say in the summary whether dependents may proceed.

## Wave review

Report `task_findings`: each covered card id mapped to that card's blocking findings. An empty list or an absent key means that card is clean. The union of the lists, in order, equals `findings`.

A cited failed gate receipt needs a BLOCKED verdict. Attribute the failure in `task_findings` to the responsible cards. When a held chain caused it, key the held tip.

## Repair-diff check and re-review of a fix round

Review only the fix range against the findings it answers, and the rejected findings the brief lists. For each finding, report fixed, not fixed or regressed. Open a new finding only for a defect the fix introduced. Do not reopen settled code.

Put `repair_check: true` in the report body. A BLOCKED check keys `task_findings` on the chain tip: the repair card, or the card itself when no repair covers it. Never key a card a repair covers.
