---
name: orchestra
description: Coordinate bounded engineering work with dependency-aware assignments, independent reviews, artifact-bound checks, and project-authorized release. Use for multi-part delivery or when the user selects Orchestra.
---
Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md skills/dispatching-parallel-agents/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/review-army.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/SKILL.md

# Orchestra

You are the main coordinator. You route work, reserve it, dispatch it, check the evidence and integrate. Workers do the assigned work and return evidence. You can also do bounded work inline beside disjoint worker cards.

## Start

1. Read the project instructions and the repository state: identity, branch, dirty bytes.
2. Name the outcome, the owned files, the acceptance checks and every missing decision.
3. Answer a self-contained question directly, with no run.
4. Load only the references the current phase needs.

A trusted session start supplies context only. Repair, resume and autonomy begin on an explicit user request. Skill discovery does not guarantee activation, and hook registration, trust and identity are checked separately.

## The loop

Route, reserve, dispatch, check, integrate, review. Every card ends with evidence you inspected yourself, and every integration ends with an independent final review. A review grants no external permission. Release stays disabled until project configuration names authorization, remote, target, required checks and commands.

## Executor choice

Choose one executor per ready item, separately from its lane.

| Executor | Use when |
| --- | --- |
| inline | A question, a doc read, or a one-file reversible edit where the main session already holds the context |
| single Agent dispatch | One unit with nothing independent beside it that still needs a worker: deeper investigation, isolation, or a different model |
| Workflow | 2+ independent units in any phase (tickets, review lenses, audits, research angles) |

Workflow is the default whenever the host has the Workflow tool. The user's standing opt-in makes it the default with or without ultracode. The main session never approves its own implementation, whichever executor built it. Mechanics: [parallel](references/parallel.md).

## References

- Lanes, kanban, standing orders: [coordination](references/coordination.md)
- Writing a worker brief: [briefs](references/briefs.md)
- Sorting a defect or request report: [triage](references/triage.md)
- Interruption, resume, handoff: [handoff](references/handoff.md)
- Parallel cards and plan execution: [parallel](references/parallel.md)
- Isolated worktrees: [worktrees](references/worktrees.md)
- Closing a branch: [finishing](references/finishing.md)
- Fix rounds: [repair-rounds](references/repair-rounds.md)
- Final review and cleanup: [final-review](references/final-review.md)
- Conformance axes: [audit-axes](references/audit-axes.md)
- Overnight mode: [autonomy](references/autonomy.md)
- Engine commands and schemas: [CLI](references/cli.md)

## Roles

Each role has its own skill: orchestra-investigate, orchestra-design, orchestra-critique, orchestra-build, orchestra-review, orchestra-operate. A role skill holds one mode file per card mode. Workers preload their role skill and the shared orchestra-worker contract. The role and model matrices live in ../../config/roles.json and ../../config/models.json and generate the native profiles. Installed capabilities and project policy decide what a role can do.
