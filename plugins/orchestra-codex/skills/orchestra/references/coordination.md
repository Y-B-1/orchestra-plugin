Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/triage/AGENT-BRIEF.md skills/productivity/writing-for-agents/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/coordination.md

# Coordinator procedure

Inspect project rules, repository identity, branch and dirty bytes first. Preserve existing work. Split the request into outcomes and size each item, not the whole message. Settle facts from code before asking for product decisions. Record each settled decision without widening scope.

## Lanes

Route by readiness and consequence. A lane is a routing choice, never an approval.

| Lane | Trigger | Minimum contract |
| --- | --- | --- |
| answer | Self-contained question | Direct answer, no run |
| investigate | Unknown premise, API or behavior | Investigator, code or docs mode; evidence before design |
| direct | Settled, bounded, low-risk change | Goal, ownership, acceptance checks, independent review |
| design | A product choice remains | Designer-planner in product mode, then design mode; wait for the needed decisions |
| plan | Approved substantial design | Designer-planner in plan mode, then independent critic challenge |
| bug | Defect | Investigator diagnosis and a failing behavior check before any repair |
| review | Existing artifact | Independent code-reviewer; critic for a named conformance axis |
| full-test | Explicit owner request | Operator gate mode with the requested full commands |

Unknown requirements go to design, dependency mistakes to planning, checked code defects to builder repair. First implementations use the implementation, frontend, sensitive or mechanical presets.

## Inline work

Executor choice is in SKILL.md. Inline work runs beside disjoint workers. Reserve it with `inline TASK`, then report under your real actor identity and returned token. The engine applies the same ownership, resource, dependency, capacity and lease checks as for a worker. Never edit a worker-owned file inline.

## Kanban

Columns are role assignments, not sequence barriers. A card holds role and mode, input artifact, dependencies, files or resources, and acceptance criteria. States: queued, running, reported, repairing, accepted. Reported means work returned; accepted means you checked the evidence and independent review passed.

- Dependent work starts after its dependencies are accepted. A review card names reported targets in `review_of` and starts when they report.
- Only running cards use capacity, inline ones included. Reported work keeps its ownership until acceptance.
- A review_of card reads its targets without taking write ownership and still reserves its own resources.
- Creating a repair suspends its ancestors as repairing and moves their reservations to the queued repair. Repair acceptance and fresh independent coverage come before ancestor acceptance.
- Before dispatch, reject unknown or cyclic dependencies, missing inputs or checks, unavailable roles or modes, overlapping ownership and exhausted capacity. The engine reserves atomically; prose scheduling is no lock.
- Early independent review goes to consequential foundations. Group low-risk related tickets under one review with stated coverage. Every integration gets a final review and the named project checks.

Example: a settings request makes I1 investigate, D1 design, P1 plan, B1 API build, B2 UI build, R1 checkpoint review of B1, G1 gates and R2 final review. R1 starts when B1 reports while B2 runs. An unrelated docs card runs alongside, on different paths.

## Standing orders

At run start write `<state>/standing-orders.md`, copying the binding project rules verbatim (path rules, authorization limits, design vocabulary, policy revision). Paste it into every brief under `## Standing orders (verbatim)`, followed by a `sha256:` line of the file. A rule that constrains a worker must be inside the brief; a link or a standing file does not reach an empty context. With mods, agent.spawn appends the file.

## Findings and interruption

Check each finding against source and try to refute it. A confirmed defect returns to the builder with the exact artifact, scenario and scope. A spec contradiction or missing decision returns to design; a task or dependency flaw to planning, then critic challenge. Never ask a builder to implement contradictory requirements. After a change, invalidate and rerun the affected reviews and gates.

On interruption or lease loss, stop dispatch. Late reports stay historical and advance nothing. Resume only on explicit request, after checking artifacts and live workers (references/handoff.md). Overnight runs follow references/autonomy.md; conformance axes are in references/audit-axes.md.

## Release and bypass

At most one terminal operator release card belongs to a run, dispatched before the permit is requested. Final review covers every pre-release card; release execution comes after. A later intact BLOCKED verdict supersedes older CLEAN coverage of the same category and artifact.

A `gh api` merge or release, or an MCP or terminal tool that pushes or merges, is no way around the guard. Use the guarded path. Procedure binds here; the guard does not enforce it.

Engine commands and schemas: references/cli.md, or `scripts/orchestra.py --help` from the plugin root.
