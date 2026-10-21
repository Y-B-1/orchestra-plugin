Source: derived from obra/superpowers@8ca22dba9a94 skills/dispatching-parallel-agents/SKILL.md skills/subagent-driven-development/SKILL.md skills/executing-plans/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/review-army.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/parallel.md

# Parallel dispatch and plan execution

## Independence test

Run cards together only when they touch different files and resources, need no result from each other, and own no shared state. Anything else runs in dependency order. Only the main changes coordinator state.

Each brief is focused and self-contained, names one output and its constraints, and follows briefs.md.

## Worth a worker

A worker costs about 100 seconds before it saves any: setup, brief, then the worktree check, merge and removal. In the 2.5 benchmark a 320-line unit took 48 s inline and 85 s in a builder, and two medium units ran faster in sequence than split. Split builder units across workers only in a large run. Escalate a medium run with `route --size large` once two or more disjoint units each reach about 600 lines, where the benchmark measured parallel builders 40% faster. Read-only side work (an investigator search, a docs lookup, an operator gate) runs as a background worker beside inline work at any size. When the main session nears its context ceiling, send the remaining units to builders, even a single one. `max_workers` in the policy caps running cards, inline ones included; the owner sets it to what the device and usage limits allow. Launch Agent workers with `run_in_background: true` when you will keep working or end the turn. After you launch a Workflow or a background Agent, start your inline card in the same turn. When nothing is left but waiting, end the turn: the harness wakes the session when a background worker finishes. Never poll or sleep.

## Workflow script

Each `agent()` call sets `agentType` to the card's agent file and a brief whose first lines carry the `Mode:` line. The agent file is `orchestra:<role>-<mode>` when that file exists (`builder-mechanical`, `builder-cleanup`, `code-reviewer-standards` for the standards lens, `code-reviewer-medium` for a combined pre-PR review, `investigator-code`), and `orchestra:<role>` otherwise. The file pins model, effort and tools; set no model or effort override. Concurrent editors set `isolation: 'worktree'` (references/worktrees.md). The script holds no coordinator state: reserve every card before the script and record every report after it.

Every Opus repair card is added after the pre-PR review and goes through the Agent tool with the model override, never through a script (references/repair-rounds.md). Dispatch it only after the accept step of coordination.md.

## After return

Merge and dedupe findings that name the same cause. Check for conflicts between the returned diffs. Spot-check each report against the artifact and its logs before you accept it; a success message is no evidence. A report that lacks what its brief required is not accepted: dispatch the card once more, and if it is still short, record that slice as an open gap that never counts as passed. A worker that dies or times out gets at most two re-dispatches, the first with a smaller scope; then hold the card and re-cut the plan.

## Review package

For each reported card write `<state>/review-packages/<card>/`: the brief, the report with its `SELF_REVIEW:` line, the base and head commits, the diff, and the command logs. The pre-PR reviewer reads the packages and the artifact, never the builder's conversation.

## Plan execution

Take tickets in plan order, each from its own brief and base commit, as engine cards. With three or more similar tickets, run the first alone to an accepted result and fix the brief before you dispatch the rest. The plan already groups them into PRs. Ready independent cards run together; dependent cards wait for their accepted prerequisites. A card is complete when its contract holds: every named check ran and passed, every expected output was compared, every deviation has a recorded ruling. A worker that finds a plan defect returns BLOCKED naming it. You record the ruling, or route the defect to planning, before work continues.
