Source: derived from mattpocock/skills@d81f3a183412 skills/engineering/code-review/SKILL.md (MIT); github/spec-kit@ae5ade7234be templates/commands/analyze.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-critique/references/standards.md

# Critic: standards mode

Audit the change against the repository's documented rules. This axis asks only whether the code follows the standards; whether it does what was asked belongs to the spec axis, a separate run.

## Sources

Read the binding rules first: the project instructions, path rules, the domain glossary and vocabulary file, contributing and coding-standard files, and the standing orders in the brief. Cite the rule file and the rule text for every finding. Do not invent project policy.

## Checks

- Scope: the change stays inside the owned paths and the approved ask.
- Domain vocabulary: the change uses the glossary terms. The same concept under a second name is drift.
- Dependency direction: imports and calls follow the layering the rules set.
- Generated and source authority: generated files are regenerated, never hand-edited, and the source of truth is the file the rules name.
- Accessibility and any other standard the brief names.
- Rules the project marks as binding or never, such as staging, branches, models or private paths.

## Precedence

A rule written as a hard requirement (must, never, always) is non-negotiable. A change that conflicts with one is a top-ranked finding. Never dilute or reinterpret a rule to let a change pass. If the rule itself looks wrong, report that as a decision for design or the user; the audit does not change policy.

A documented repository rule overrides any general baseline. Where the repository documents nothing, you may add a general craft concern as a judgement call. Label it judgement, never present it as a violation, and drop it where the repository endorses the pattern. Skip anything a linter or formatter already enforces.

## Report

Group findings by rule. For each, give the rule, the violating line or hunk, and whether it is a hard violation or a judgement call. Report the rules you could not locate as an evidence gap.
