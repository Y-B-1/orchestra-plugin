Source: derived from obra/superpowers@8ca22dba9a94 skills/dispatching-parallel-agents/SKILL.md skills/subagent-driven-development/SKILL.md skills/executing-plans/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/review-army.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/parallel.md

# Parallel dispatch and plan execution

## Independence test

Run cards together only when they touch different files and resources, need no result from each other, and own no shared state. Anything else runs in dependency order. Only the main changes coordinator state.

Each brief is focused and self-contained, names one output and its constraints, and follows briefs.md.

## Worth a worker

**Waves checkpoint.** After the plan and before the first start, run `waves`: it prints reservation overlaps, dependency chains, the waves (each one independent and disjoint, cut to `max_workers` and `max_worktrees`) and `startable_now`. Start each wave whole with `wave [--inline ID] [--emit] ID ...` (`--emit` prints each card's `agent_call` and prompt with its `Assignment:` line): one card inline, the rest to workers in one Workflow, in the same turn. `dispatch` and `inline` refuse a lone start while another disjoint card could start beside it; `--serial REASON` overrides, and the reason goes to the progress ledger. This replaces the 2.5 benchmark rule (medium units in sequence): the owner chose parallel waves at every size. A worker still costs about 100 seconds of setup, so a wave of one small card runs inline. Read-only side work (an investigator search, a docs lookup, an operator gate) runs as a background worker beside inline work at any size. When the main session nears its context ceiling, send the remaining units to builders, even a single one. `max_workers` in the policy caps running cards, inline ones included; the owner sets it to what the device and usage limits allow. `max_worktrees` (default 3) caps running builder cards that are not inline; read-only roles and inline cards do not count. Launch Agent workers with `run_in_background: true` when you will keep working or end the turn. After you launch a Workflow or a background Agent, start your inline card in the same turn. When nothing is left but waiting, end the turn: the harness wakes the session when a background worker finishes. Never poll or sleep.

## Workflow script

Each `agent()` call sets `agentType` to the card's agent file and a brief whose first lines carry the `Mode:` line. The agent file is `orchestra:<role>-<mode>` when that file exists (`builder-mechanical`, `builder-cleanup`, `code-reviewer-standards` for the standards lens, `code-reviewer-medium` for a combined pre-PR review, `investigator-code`), and `orchestra:<role>` otherwise. The file pins model, effort and tools; set no model or effort override. Concurrent editors set `isolation: 'worktree'` (references/worktrees.md). The script holds no coordinator state: reserve every card before the script and record every report after it.

Every Opus repair card is added after the pre-PR review and goes through the Agent tool with the model override, never through a script (references/repair-rounds.md). Dispatch it only after the accept step of coordination.md.

## After return

Merge and dedupe findings that name the same cause. Check for conflicts between the returned diffs. Spot-check each report against the artifact and its logs before you accept it; a success message is no evidence. A report that lacks what its brief required is not accepted: dispatch the card once more, and if it is still short, record that slice as an open gap that never counts as passed. A worker that dies or times out gets at most two re-dispatches, the first with a smaller scope; then hold the card and re-cut the plan.

## Review package

For each reported card write `<state>/review-packages/<card>/` (`package TASK` writes one from engine facts; `ledger` prints the BUILD-LEDGER rows): the brief, the report with its `SELF_REVIEW:` line, the base and head commits, the diff, and the command logs. The pre-PR reviewer reads the packages and the artifact, never the builder's conversation.

## Plan execution

Take tickets in plan order, each from its own brief and base commit, as engine cards. With three or more similar tickets, run the first alone (`--serial first-of-similar`) to an accepted result and fix the brief before you dispatch the rest. The plan already groups them into PRs. Ready independent cards run together; dependent cards wait for their accepted prerequisites. A card is complete when its contract holds: every named check ran and passed, every expected output was compared, every deviation has a recorded ruling. A worker that finds a plan defect returns BLOCKED naming it. You record the ruling, or route the defect to planning, before work continues.
