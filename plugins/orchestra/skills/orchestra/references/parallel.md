Source: derived from obra/superpowers@8ca22dba9a94 skills/dispatching-parallel-agents/SKILL.md skills/subagent-driven-development/SKILL.md skills/executing-plans/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/review-army.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/parallel.md

# Parallel dispatch and plan execution

## Independence test

Run cards together only when they touch different files and resources, need no result from each other, and own no shared state. Anything else runs in dependency order. Reserve every card in the engine first; reject cycles and overlaps. Only the main changes coordinator state.

Each brief is focused and self-contained, names one output and its constraints, and follows briefs.md.

## Workflow script

Each `agent()` call sets `agentType: 'orchestra:<role>'`, the effort from the model matrix, and a brief whose first lines carry the `Mode:` line. Concurrent editors set `isolation: 'worktree'` (references/worktrees.md). The script holds no coordinator state: you reserve before it and record every report after it.

A round-4 repair goes through the Agent tool with the model override, never through a script (references/repair-rounds.md). Codex has no Workflow tool; dispatch the same roles in parallel one by one.

## After return

Merge and dedupe findings that name the same cause. Check for conflicts between the returned diffs. Spot-check each report against the artifact and its logs before you accept it; a success message is no evidence.

## Review package

For each reported card write `<state>/review-packages/<card>/`: the brief, the report, the base and head commits, the diff, and the command logs. The independent reviewer reads the package and the artifact, never the builder's conversation.

## Plan execution

Take tickets in plan order, each from its own brief and base commit, as engine cards. Ready independent cards run together; dependent cards wait for their accepted prerequisites. A card is complete when its contract holds: every named check ran and passed, every expected output was compared, every deviation has a recorded ruling. A worker that finds a plan defect returns BLOCKED naming it. You record the ruling, or route the defect to planning, before work continues.
