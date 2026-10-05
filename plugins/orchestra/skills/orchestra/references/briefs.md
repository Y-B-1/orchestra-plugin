Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/implementer-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/triage/AGENT-BRIEF.md skills/productivity/writing-for-agents/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/briefs.md

# Brief writing

One brief per worker, one responsibility per brief. Write it for a reader with empty context, durable and behavioral: name interfaces and outcomes, and point to files by path instead of copying them.

1. Objective: a summary, the current against the desired behavior, and what is out of scope.
2. `Mode:` line (a review brief adds `Lens:`, a lens name or `specialist:<name>`), the immutable starting artifact and the requested output path.
3. Ownership: files and resources, sibling ownership, worktree, prerequisites.
4. Acceptance: criteria a command can check, each ending in a stated done condition.
5. Rules: the binding project rules, path rules and design vocabulary, carried inline after you read the source. A link alone does not carry a rule into an empty context. Paste the standing orders as coordination.md describes.
6. Tools, authorization limits and the report contract.
7. Builder briefs add `## Keep` and `## Remove`: exact paths, symbols or behaviors, or `none`.

Review briefs carry the current gate receipt ids, the held log and `## Known findings`, the output of `finding list --for-brief`.

Plugin root: name the directory holding `skills/` and `scripts/`. The worker reads its role skill from `<root>/skills/` and runs `<root>/scripts/orchestra.py`.

The worker contract lives in the orchestra-worker skill, so a brief omits it. The engine rejects a card whose brief file lacks its `Mode: <mode>` line.
