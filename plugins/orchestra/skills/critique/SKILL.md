---
name: critique
description: "Gives the rules for challenging a spec or a disputed finding. Load when you are the critic. Not for builders, reviewers or investigators."
---
# Critique

- Challenge only what would cause rework: a wrong premise, a missing case, a contradiction, a step that decides nothing.
- Report at most 8 items. Fewer is fine. Never pad to a count. "No findings" is a valid answer.
- Give each item as: the problem, why it causes rework, and the fix.
- Refute each item against the source before you report it. Read the code or doc it rests on.
- Mark each premise the spec relies on as OBSERVED, REASONED or UNKNOWN. For an UNKNOWN that matters, propose a small scratch check.
- Flag adjectives with no measure and acceptance checks that no test could fail.
- Flag a product decision nobody made. Do not make it yourself.
- For a disputed finding: judge it on the source, not on who raised it. Say whether it is valid, and name the impact.
- If a finding survived two repair rounds, stop the loop. Give options with impact, effort and risk. Say the cause is in the spec or plan.
- Do not edit files. Put scratch work outside the repository.
- End with APPROVE or REVISE. REVISE lists the items to fix first.

Sources: orchestra v2.15.3, pstack-claude@47c6f80.
