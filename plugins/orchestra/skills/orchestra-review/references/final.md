Source: derived from obra/superpowers@8ca22dba9a94 skills/requesting-code-review/code-reviewer.md skills/subagent-driven-development/task-reviewer-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/code-review/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/SKILL.md review/sections/plan-completion.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-review/references/lens-adversarial.md (MIT); github/spec-kit@ae5ade7234be .github/skills/code-review/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/final.md

# Code reviewer: final mode

Review the full integration diff against the named base and the current artifact. Include how tickets interact, not only each ticket alone.

## Lens

The brief's `Lens:` line names one lens file: `correctness.md`, `architecture.md`, `security.md` or `cleanliness.md`. Open that file and review only through it.

A `Lens:` line of `specialist:<name>` names a section of `specialists.md` instead. Open that file and review only through the named section. Tag each finding with the closest category from the table below, and set `categories` to the ones you used.

A final brief with no `Lens:` line is a blocker. Report `STATUS: BLOCKED` and name the missing line. Do not review all lenses to make up for it.

| Lens file | Categories you report |
|---|---|
| `correctness.md` | requirements, correctness, tests, standards |
| `architecture.md` | architecture |
| `security.md` | security |
| `cleanliness.md` | cleanup |

Set `categories` in the verdict to the row for your lens and no other. Findings outside your lens go in the summary as a note. They do not change your verdict.

## Whole-integration checks

- Read the diff from the base to the artifact, not ticket by ticket.
- Find contracts that two tickets each assume differently.
- Find the same symbol or file changed by more than one ticket.
- Confirm that every requirement in the approved ask is met by code in the diff.

## Verdict

Echo the `artifact` output as the base skill says. Set `final` to true. Return BLOCKED if any finding in your categories is an open blocker.
