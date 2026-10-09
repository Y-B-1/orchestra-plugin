Source: derived from obra/superpowers@8ca22dba9a94 skills/requesting-code-review/code-reviewer.md skills/subagent-driven-development/task-reviewer-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/code-review/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/SKILL.md review/sections/plan-completion.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-review/references/lens-adversarial.md (MIT); github/spec-kit@ae5ade7234be .github/skills/code-review/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/final.md

# Code reviewer: final mode

This is the pre-PR review. Review the full integration diff against the named base and the current artifact. Include how tickets interact, not only each ticket alone. A brief that names a fix range is a fix re-review (below).

## Lens

The brief's `Lens:` line names one lens file: `correctness.md`, `security.md` or `standards.md`. Open that file and review only through it, with the checklist files the table names for it. The coordinator derives which lenses run from the diff; you review the one your brief names.

A `Lens:` line of `specialist:<name>` names a section of `specialists.md` instead. Open that file and review only through the named section. Tag each finding with the closest category from the table below, and set `categories` to the ones you used.

A final brief with no `Lens:` line is a blocker. Report `STATUS: BLOCKED` and name the missing line. Do not review all lenses to make up for it.

| Lens file | Categories you report | Checklists it also reads |
|---|---|---|
| `correctness.md` | requirements, correctness, tests, architecture | `architecture.md` |
| `security.md` | security | none |
| `standards.md` | standards, cleanup | `cleanliness.md` |

A `Lens: combined` line runs every lens the diff needs in one card, for a diff of 400 changed lines or fewer. The brief also carries a `Required categories:` line, copied from the `lenses` that `prepr` printed. Open `correctness.md`, plus `security.md` and `standards.md` when the list names their categories, with the checklists the table names for each. Set `categories` to exactly that list. A combined brief with no `Required categories:` line is a blocker, like a missing `Lens:` line.

With a single lens, set `categories` in the verdict to the row for your lens and no other. Findings outside your lens go in the summary as a note. They do not change your verdict.

## Whole-integration checks

- Read the diff from the base to the artifact, not ticket by ticket. Cover every task, held ones included, and read the held log and the gate receipts the brief carries.
- Find contracts that two tickets each assume differently.
- Find the same symbol or file changed by more than one ticket.
- Confirm that every requirement in the approved ask is met by code in the diff.
- Cite the operator's gate receipt in `gate_receipts`. Run no full suite; the guard denies suite commands while a current receipt exists. A cited failed receipt is a blocking finding for the correctness lens.

## Attribution

- Put each blocking finding in `task_findings` under the chain tip whose change introduced it. A key that is not a chain tip is refused.
- Address every held tip: a blocking finding under it, or an entry in `cleared` with a reason. The correctness lens judges the held finding itself. Another lens clears it with a reason scoped to its own categories, such as "no security defect".
- A defect no card's change introduced is out of scope. List it in `out_of_scope`, a list of strings that never changes the verdict. A defect from a card that is not a builder goes there too, naming that card.

## Verdict

Echo the `artifact` output as the base skill says. Set `final` to true. Return BLOCKED if any finding in your categories is an open blocker.

## Fix re-review

When the brief names a fix range and `repair_check`, review only that range against the findings it answers and the rejected findings the brief lists. For each finding, report fixed, not fixed or regressed. Open a new finding only for a defect the fix introduced. Do not reopen settled code.

Put `repair_check: true` in the report body and set `final` to false. Key a BLOCKED `task_findings` on the chain tip: the repair card. Never key a card a repair covers.
