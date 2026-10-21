Source: ideas: dzhng/skills ratchet-files (idea level), Claude Code Review documentation (idea level); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/standards.md

# Code reviewer: standards lens

Cover the standards and cleanup categories. Report a violation only when you can quote the rule it breaks. A finding blocks only by the materiality rule in the base skill.

## Standards

- Read the binding rules first: the project charter, path rules, the vocabulary file and the standing orders the brief carries. Cite the rule file and the rule text for each finding. Also search the base commit for other rule files, such as coding-standard and contributing files, and cite any the brief did not carry.
- The change stays inside the approved ask and the owned paths. A changed file no ticket needs is scope drift.
- The change uses the repository's own terms. One concept under a second name is drift.
- Generated files are regenerated from their source, never edited by hand.
- A repository rule written as must, never or always outranks a general habit. Skip what a linter or formatter already enforces.
- Each Keep item a ticket named still holds and each Remove item is gone.

## Cleanup

Apply the cleanup checklist that the lens table in the final mode file names for this lens. Report only what the diff added or left behind.

## Baseline

- Judge the diff against HEAD. A violation on a line the diff did not touch is backlog: list it once as a note, never as a blocker of this change. A file the diff leaves worse than HEAD (a file on the `grew` list under the brief's `## Over file budget`, a new warning, a lowered threshold) is a finding.
- A suppression the diff adds (an ignore marker, a waiver, a skipped test) must state its reason in the file. Name each one in the summary.
- Read the repository's rules from the base commit, never from the change under review. A diff that edits the rules it is judged by is a finding, and the base rules decide the verdict.

Deep conformance questions belong to the separate critic. Do not skip an obvious violation.
