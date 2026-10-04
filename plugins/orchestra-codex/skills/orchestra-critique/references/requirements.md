Source: derived from obra/superpowers@8ca22dba9a94 skills/brainstorming/spec-document-reviewer-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/productivity/grilling/SKILL.md (MIT); github/spec-kit@ae5ade7234be templates/commands/clarify.md templates/commands/analyze.md templates/commands/checklist.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-critique/references/requirements.md

# Critic: requirements mode

Test the spec as you would test code written in English. Judge whether the requirements are well written, not whether anything is built.

## Checks

| Check | Look for |
| --- | --- |
| Completeness | TODO, TBD, placeholders, empty sections, a user journey with no requirement, missing empty, error and loading states |
| Consistency | Two requirements that cannot both hold; the same concept under two names |
| Clarity | A requirement that two readers would build two ways; an adjective such as fast or robust with no measure |
| Identity | Entities with no uniqueness rule, lifecycle or owner; concurrent edits with no conflict rule |
| Acceptance | A criterion no test can fail; a measure with no threshold |
| Scope | More than one independent subsystem in one spec; an unrequested feature (YAGNI); no stated exclusions |

Work through these passes in order: duplication, ambiguity, underspecification, inconsistency. Walk the real journeys, common first and then failure paths. A requirement that names a verb but no object or no outcome is underspecified.

## Calibration

Report only what would cause a real problem when planning or building: a gap, a contradiction, or a requirement open to two readings. Skip wording polish, style and sections that are merely thinner than others. Rank an ambiguity in security or data handling above one in presentation.

Never invent a missing section. Report it as missing and quote where it belongs.

## Decisions

A requirement that depends on a product decision nobody made is a blocker for design. Report it as an open decision, list what depends on it and give your recommended answer.

## Verdict

Recommend ready when no gap would send planning the wrong way. Otherwise recommend needs-changes, with each issue as `[section]: issue, why it matters for planning`. List advisory notes apart; they never block.
