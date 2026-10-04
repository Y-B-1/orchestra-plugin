---
name: orchestra
description: Coordinate bounded engineering work with dependency-aware assignments, independent reviews, artifact-bound checks, and project-authorized release. Use for multi-part delivery or when the user selects Orchestra.
---

Sentinel: orchestra/SKILL.md
Stub: B4 skeleton; ticket S1 rewrites this file and removes this line.

# Orchestra

The main session coordinates and can perform bounded work inline; workers finish assigned work and return evidence. Before each action, choose inline or worker execution from task readiness, risk, context and independent work. Inline work can run alongside disjoint worker assignments. Use the user's project rules and authorization boundaries. Opening a trusted session supplies coordinator context only; do not repair, resume, or start an autonomous loop without a request. Skill discovery alone does not guarantee activation. Native hook registration, enablement, trust and identity must be checked separately.

Start by reading applicable project instructions and current repository state. Identify the requested outcome, bounded ownership, acceptance checks and missing decisions. Answer self-contained questions directly. Load references only when their phase applies:

- Routing, role columns and continuous ready dispatch: [coordination](references/coordination.md).
- Worker assignment: [briefs](references/briefs.md). Workers carry their own contract in the orchestra-worker skill.
- Triage: [triage](references/triage.md). Resume and handoff: [handoff](references/handoff.md).
- Parallel dispatch: [parallel](references/parallel.md). Worktrees: [worktrees](references/worktrees.md).
- Finishing a branch: [finishing](references/finishing.md). Fix rounds: [repair-rounds](references/repair-rounds.md).
- Final review lenses and cleanup: [final-review](references/final-review.md). Conformance axes: [audit-axes](references/audit-axes.md).
- Autonomous mode: [autonomy](references/autonomy.md).
- Run commands and task/review schemas: [CLI](references/cli.md).

Role methods live in the role skills (orchestra-investigate, orchestra-design, orchestra-critique, orchestra-build, orchestra-review, orchestra-operate), one mode file per card mode. Workers preload their role skill; every brief carries a `Mode:` line, and a final-review brief a `Lens:` line. Do not load every reference for a tiny request. Canonical roles and provider matrices live in ../../config/roles.json and ../../config/models.json. They generate native profiles; installed capabilities and project policy still determine what a role can do.

Always use an independent final review of integration. A review never grants external permission. Release remains disabled until project configuration names authorization, remote, target, required checks and commands. Report native discovery or trust limits honestly.
