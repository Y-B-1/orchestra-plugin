Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/triage/AGENT-BRIEF.md skills/productivity/writing-for-agents/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/coordination.md

# Coordinator procedure

Preserve existing work. Split the request into outcomes and size each item, not the whole message. Settle facts from code before asking for product decisions. Record each settled decision without widening scope.

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

Inline work runs beside disjoint workers. Reserve it with `inline TASK`, then report under your real actor identity and returned token. The engine applies the same ownership, resource, dependency, capacity and lease checks as for a worker. Never edit a worker-owned file inline.

## Kanban

Columns are role assignments, not sequence barriers. A card holds role and mode, input artifact, dependencies, files or resources, and acceptance criteria. States: queued, running, reported, repairing, held, accepted. Reported means work returned; accepted means you checked the evidence and independent review passed. Held is a chain that left the repair ladder (references/repair-rounds.md); it reserves nothing and a dependency on it counts as met.

- Dependent work starts after its dependencies are accepted. A review card names reported targets in `review_of` and starts when they report.
- Only running cards use capacity, inline ones included. Reported work keeps its ownership until acceptance.
- A review_of card reads its targets without taking write ownership and still reserves its own resources.
- Creating a repair suspends its ancestors as repairing and moves their reservations to the queued repair. Repair acceptance and fresh independent coverage come before ancestor acceptance.
- Before dispatch, reject unknown or cyclic dependencies, missing inputs or checks, unavailable roles or modes, overlapping ownership and exhausted capacity. The engine reserves atomically; prose scheduling is no lock.

Example: a settings request makes I1 investigate, D1 design, P1 plan, B1 API build, B2 UI build, R1 checkpoint review of B1, G1 gates and R2 final review. R1 starts when B1 reports while B2 runs. An unrelated docs card runs alongside, on different paths.

## Waves

Label builder implementation cards with `wave`. When a wave's builders have reported, one checkpoint review covers it with `review_of: ["wave:W"]`; its report maps each covered card to its blocking findings in `task_findings`. A consequential foundation is a wave of one, reviewed before dependent waves start. A card added to a wave that already has a review is refused: start a new wave.

A gate between waves runs only when the next wave depends on its code: a next-wave card lists a wave card in `dependencies`, or names in `files` or `inputs` a path a wave card owns. Otherwise the operator gates the candidate once in the final phase. Gate after the builders report and before the wave review, so the reviewer cites the receipt. A failed gate is a finding: the reviewer returns BLOCKED and attributes it to the responsible cards, a held chain's tip included. `status` shows each wave and whether the next one depends on it.

One loop per wave. After any review receipt, work in this order: record ledger rejections, accept every acceptable card whose evidence a repair would make stale, then add and dispatch repairs. The engine refuses a repair that overlaps a card you could still accept: "Accept X first". Each card with a remaining finding gets one repair card. Then one repair-diff check covers every repair card and its chain ancestors, plus each card whose findings were all rejected; its brief names the fix range and the rejected findings, and its report carries `repair_check: true`. A chain still blocked after the check is held, never reviewed a third time.

A wave member parked at an approval boundary before the review runs leaves the review never ready. Park the queued wave review and add a replacement whose `review_of` names the other members; the parked member gets its own review once unparked. Clear the parked original with `supersede TASK`.

## Standing orders

At run start write `<state>/standing-orders.md`, copying the binding project rules verbatim (path rules, authorization limits, design vocabulary, policy revision). Paste it into every brief under `## Standing orders (verbatim)`, followed by a `sha256:` line of the file. With mods, agent.spawn appends the file.

## Findings and interruption

Check each finding against source and try to refute it. Record a refuted finding as `rejected` and a postponed one as `deferred` with `orchestra.py finding add`; `finding list --for-brief` prints the block reviewers must not re-raise. A rejection never accepts a card: the repair-diff check does. A confirmed defect goes to builder repair (references/repair-rounds.md). A spec contradiction or missing decision returns to design; a task or dependency flaw to planning, then critic challenge. Never ask a builder to implement contradictory requirements. After a change, invalidate and rerun the affected reviews and gates.

On interruption or lease loss, stop dispatch. Late reports stay historical and advance nothing. Resume follows references/handoff.md. Overnight runs follow references/autonomy.md; conformance axes are in references/audit-axes.md.

## Release and bypass

At most one terminal operator release card belongs to a run, dispatched before the permit is requested. Final review covers every pre-release card; release execution comes after. A later intact BLOCKED verdict supersedes older CLEAN coverage of the same category and artifact.

A `gh api` merge or release, or an MCP or terminal tool that pushes or merges, is no way around the guard. Use the guarded path. Procedure binds here; the guard does not enforce it.

Every command and schema is in references/cli.md, or in `scripts/orchestra.py --help` from the plugin root.
