Source: derived from obra/superpowers@8ca22dba9a94 skills/requesting-code-review/code-reviewer.md skills/subagent-driven-development/task-reviewer-prompt.md skills/subagent-driven-development/re-review-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/code-review/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/SKILL.md review/sections/plan-completion.md (MIT); github/spec-kit@ae5ade7234be .github/skills/code-review/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/checkpoint.md

# Code reviewer: checkpoint mode

Review the ticket or review group the brief names against its acceptance criteria. A group lists every ticket it covers. Review each one.

## Procedure

1. Read the acceptance criteria and the ownership list. Then read the diff.
2. Sort every gap into one of three classes. Missing: a criterion the code does not meet. Extra: behavior or files nobody asked for. Misunderstood: code that meets the wording and misses the intent.
3. Check the evidence. Each command the report cites must name a real command, its exit and a log path. Flag proof that is missing or that predates the last edit. The operator gate reruns the builder's acceptance suite; you do not. You do run targeted probes, comparisons and counterexamples.
4. Sibling-owned paths stay untouched.
5. Check the tests:
   - The ticket has a test for what the code must do and a test for what it must prevent.
   - Test names and changed wording use the repository's own terms.
6. A consequential foundation gets this review before dependent work starts. Say in the summary whether dependents may proceed.

## Re-review of a fix round

Review only the fix range against the findings it answers. For each finding, report fixed, not fixed or regressed. Open a new finding only for a defect the fix introduced. Do not reopen settled code.
