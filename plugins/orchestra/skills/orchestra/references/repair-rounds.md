Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md skills/systematic-debugging/SKILL.md (MIT); garrytan/gstack@4015c2870b06 investigate/SKILL.md SKILL.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-correct-course/checklist.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/repair-rounds.md

# Repair ladder

The ladder has one repair, one fix re-review, then a hold. It runs after the pre-PR review and before the PR. A hold never stops a run.

| Rung | Action |
| --- | --- |
| 1 | The implementation card, on the builder default model. Its self-review is its only review before the PR. |
| 2 | One builder `repair` card per chain with a current pre-PR finding, dispatched through the Agent tool with the Opus override (`claude-opus-5-5`), never through a script. It needs checked blocking findings on a `reported` or `accepted` target without `repaired_by`. On a size run the card carries `"size": "medium"`; on a 2.4 inline route, dispatch it with `dispatch --helper REASON`. |
| 3 | One fix re-review of the fix diff only, with `repair_check: true`, by the agent `prepr` names for the fix diff, with no `Required categories:` line. CLEAN accepts the chain. |
| Hold | `orchestra.py hold TASK --finding TEXT` when the fix re-review is BLOCKED. It moves the whole chain to `held`. |

Each repair brief carries the exact artifact, the failing scenario and the scope of the defect. A second repair on a chain is refused until the owner takes it. Notes never reach the ladder.

## Held work

The hold appends `- held <id> (chain <ids>): <finding>` to `<state>/progress.md`; that is the held log. Held work reserves no files and blocks nothing else. The owner decides it: the run brief's Needs you and Held log sections carry the chain and its last finding. Completion refuses while a card is held.

## Why the ladder ends in a hold

A second failed fix usually means the cause is not the patch. Holding puts the chain, with its last finding, in front of the owner instead of looping.
