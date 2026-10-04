Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md skills/executing-plans/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/review-army.md bin/gstack-diff-scope (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/final-review.md

# Final review

Run the final review on the integrated, frozen candidate. Any later edit voids it.

## Four lenses

Dispatch four separate code-reviewer cards, one per lens: correctness, architecture, security and cleanliness. Each brief carries a `Lens:` line and covers every task in the integration. All four lens cards run every time; the size gate below decides only whether specialists run. What each lens checks lives in the orchestra-review skill.

## Routing

- Correctness findings go to builder repair under the round rules in repair-rounds.md.
- Architecture, security and cleanliness findings go to one builder cleanup card at the end. One fixer receives the complete list, because a fixer per finding rebuilds context and reruns checks each time.
- After the cleanup card, run a fresh four-lens review of the new frozen candidate. Cleanup findings that survive count as repair rounds on that card.

## Specialists

Add specialist reviewers only when `git diff --shortstat BASE..HEAD` reports more than 50 changed lines and the changed paths match the specialist's surface. Build the changed set from committed changes, the working tree and untracked files. Distinguish "could not look" (an unresolvable base, a failed command) from "nothing matched". Never read a failure to look as a clean match; stop and report it.

Brief a specialist as a code-reviewer card with `Lens: specialist:<name>`, where `<name>` is a section heading of `skills/orchestra-review/references/specialists.md` under the plugin root (frontend, visual, testing and the rest). The lens line only names the checklist; it never decides whether the card runs or what the verdict is.

Merge and dedupe findings across lenses and specialists before routing.
