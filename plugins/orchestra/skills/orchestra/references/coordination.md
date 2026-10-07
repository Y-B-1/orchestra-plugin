Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/triage/AGENT-BRIEF.md skills/productivity/writing-for-agents/SKILL.md (MIT); mattpocock/skills@2b47ffcf2385 skills/in-progress/chief-of-staff/SKILL.md skills/engineering/diagnosing-bugs/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/coordination.md

# Coordinator procedure

Preserve existing work. Split the request into outcomes and size each item, not the whole message. Settle facts from code before asking for product decisions. Record each settled decision without widening scope.

## Lanes

Route by readiness and consequence. A lane is a routing choice, never an approval.

| Lane | Trigger | Minimum contract |
| --- | --- | --- |
| answer | Self-contained question | Direct answer, no run |
| investigate | Unknown premise, API or behavior | Investigator, code or docs mode; evidence before design |
| direct | Settled, bounded, low-risk change | Goal, ownership, acceptance checks, self-review, then the pre-PR review |
| design | A product choice remains | Designer-planner in product mode, then design mode; wait for the needed decisions |
| plan | Approved substantial design, or 6+ items | Designer-planner in plan mode, then independent critic challenge |
| bug | Defect | Investigator diagnosis and a failing behavior check before any repair; after the accepted repair, a retro (Two tracks) |
| review | Existing artifact or PR candidate | Independent code-reviewer; critic for a named conformance axis |
| full-test | Explicit owner request | Operator gate mode with the requested full commands |

Unknown requirements go to design, dependency mistakes to planning, checked code defects to builder repair. First implementations use the implementation, frontend, sensitive or mechanical presets.

## Two tracks

Work two tracks. The tactical track finishes the current task. The Strategic track is to change the environment so the next task goes better. Before each piece of work, ask what would make it easier or safer, then route that change as its own card. Prefer a lint rule, a constrained API, a standards file or an automated check to more instructions.

No workarounds. When the code deviates from project convention, fix the deviation before you build features on it. Route the fix as its own card.

Retro after a bug. When a bug-lane repair is accepted, name the missing check or seam that would have caught the bug. Route adding it on the strategic track.

## Inline work

Inline work runs beside disjoint workers. Reserve it with `inline TASK`, then report under your real actor identity and returned token. The engine applies the same ownership, resource, dependency, capacity and lease checks as for a worker. Never edit a worker-owned file inline.

## Kanban

Columns are role assignments, not sequence barriers. A card holds role and mode, input artifact, dependencies, files or resources, and acceptance criteria. States: queued, running, reported, repairing, held, accepted. Reported means work returned; accepted means you checked the evidence and the builder's self-review holds on the current artifact. Held is a chain that left the repair ladder (references/repair-rounds.md); it reserves nothing and a dependency on it counts as met.

- Dependent work starts after its dependencies are accepted. A fix re-review card names the reported repair in `review_of` and starts when it reports.
- Only running cards use capacity, inline ones included. Reported work keeps its ownership until acceptance.
- A review_of card reads its targets without taking write ownership and still reserves its own resources.
- Creating a repair suspends its ancestors as repairing and moves their reservations to the queued repair. Repair acceptance and a CLEAN fix re-review come before ancestor acceptance.
- Before dispatch, reject unknown or cyclic dependencies, missing inputs or checks, unavailable roles or modes, overlapping ownership and exhausted capacity. The engine reserves atomically; prose scheduling is no lock.

Example: a settings request makes I1 investigate, D1 design, P1 plan, B1 API build, B2 UI build, G1 gate and R1 pre-PR review. B1 and B2 run together on disjoint paths, each reporting its `SELF_REVIEW:` line. G1 and R1 follow once both are accepted.

## Before the PR

Builders run their own checks and review their own diff (orchestra-build). Nothing else reviews or gates until the PR candidate is frozen. Then the operator gates the gap: the derived impact set and e2e. The full suite runs only on the owner's request. One pre-PR review follows (references/final-review.md), with lenses derived from the diff.

After the review, work in this order: record ledger rejections, accept every acceptable card, then add one repair card per chain with a remaining finding. When a repair reports, one fix re-review covers only the fix diff and the rejected findings, with `repair_check: true`. CLEAN accepts the chain. BLOCKED holds it, with no second repair unless the owner asks.

## Standing orders

At run start write `<state>/standing-orders.md`, copying the binding project rules verbatim (path rules, authorization limits, design vocabulary, policy revision). Paste it into every brief under `## Standing orders (verbatim)`, followed by a `sha256:` line of the file. With mods, agent.spawn appends the file.

## Findings and interruption

Check each finding against source and try to refute it. Record a refuted finding as `rejected` and a postponed one as `deferred` with `orchestra.py finding add`; `finding list --for-brief` prints the block reviewers must not re-raise. A rejection never accepts a card: the fix re-review does. A confirmed defect goes to the one builder repair (references/repair-rounds.md). A spec contradiction or missing decision returns to design; a task or dependency flaw to planning, then critic challenge. Never ask a builder to implement contradictory requirements. After a change, rerun the affected gates and the pre-PR review.

On interruption or lease loss, stop dispatch. Late reports stay historical and advance nothing. Resume follows references/handoff.md. Overnight runs follow references/autonomy.md; conformance axes are in references/audit-axes.md.

## Release and bypass

At most one terminal operator release card belongs to a run, dispatched before the permit is requested. The pre-PR review covers every pre-release card; release execution comes after. A later intact BLOCKED verdict outranks older CLEAN coverage of the same category and artifact.

A `gh api` merge or release, or an MCP or terminal tool that pushes or merges, is no way around the guard. Use the guarded path. Procedure binds here; the guard does not enforce it.

Every command and schema is in references/cli.md, or in `scripts/orchestra.py --help` from the plugin root.
