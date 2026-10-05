Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md skills/systematic-debugging/SKILL.md (MIT); garrytan/gstack@4015c2870b06 investigate/SKILL.md SKILL.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-correct-course/checklist.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/repair-rounds.md

# Repair ladder

The ladder has two rungs and then holds: Sonnet builder, one Opus repair, then hold. No round counter, cap or breaker applies, and a hold never stops or blocks a run.

| Rung | Action |
| --- | --- |
| 1 | The implementation card, on the builder default model. |
| 2 | One builder `repair` card, dispatched through the Agent tool with the Opus override (`claude-opus-5-5`), never through a script. It needs checked blocking findings on a `reported` or `accepted` target without `repaired_by`. |
| Hold | `orchestra.py hold TASK --finding TEXT` when the repair is still blocked by a current verdict, or the repair-diff check blocks a card with no repair. It moves the whole chain to `held`. |

Each repair brief carries the exact artifact, the failing scenario and the scope of the defect. A repair of a repair, or of a card the repair-diff check blocked, is refused during the build until the chain is held. Notes never reach the ladder.

## Held work

The hold appends `- held <id> (chain <ids>): <finding>` to `<state>/progress.md`; that is the held log. Held work blocks nothing in the build: it reserves no files and later waves run past it. The final phase clears it (references/final-review.md): a repair of the held tip, or every final lens clearing it with a reason. Completion refuses while a card is held.

## Why the ladder ends in a hold

A second failed fix usually means the cause is not the patch. Holding keeps the run moving and puts the chain, with its last finding, in front of the final lenses and the user's brief; the deadline is the only outer limit.
