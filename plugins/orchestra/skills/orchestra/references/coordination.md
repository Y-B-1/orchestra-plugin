# Main coordinator procedure

Inspect project rules, repository identity, branch and dirty bytes first. Preserve existing work. Split the request into outcomes; size each item, not the whole message. Resolve facts from code before asking for product decisions. Record settled decisions without silently broadening scope.

## Route by readiness and consequence

| Lane | Trigger | Minimum contract |
| --- | --- | --- |
| answer | Self-contained question | Direct answer; no run ceremony |
| investigate | Unknown premise/API/behavior | Investigator code/docs mode; evidence before design |
| direct | Settled, bounded low-risk change | Goal, ownership, acceptance checks, independent review |
| design | Product choice remains | Founder as needed, designer-planner design mode; wait for necessary decisions |
| plan | Approved substantial design | Designer-planner plan mode, independent red team |
| bug | Defect | Investigator diagnosis and failing behavior evidence before builder repair |
| review | Existing artifact | Independent code-reviewer; auditor for named conformance axis |
| full-test | Explicit owner request | Gatekeeper with requested full commands; no silent suite expansion |

Lanes are routing choices, not automatic approval. Unknown requirements go to design; dependency mistakes go to planning; checked code defects go to builder. Use first implementation presets until independently checked findings justify repair.

## Kanban and dependency graph

The board's columns are role assignments, not sequence barriers. Cards contain role/mode, input artifact, dependencies, exclusive files/resources and acceptance criteria. Their states are queued, running, reported, accepted. Reported means work returned; accepted means the coordinator checked the evidence and completed required independent review. Dependent work starts only after its dependencies are accepted.

Before dispatch, reject unknown or cyclic dependencies, missing inputs/checks, unavailable roles/modes, overlapping ownership/resources and exhausted capacity. Reserve ownership atomically through the structured engine; prose scheduling is not a lock. Track worker identity, activity evidence and session lease. The main alone changes coordinator state and schedules workers.

Example: a settings request produces I1 investigator, D1 design, P1 plan, B1 API builder, B2 UI builder, R1 checkpoint, G1 gates and R2 final review. The directed acyclic graph is I1 → D1 → P1; P1 → B1 and B2; B1 → R1; B1+B2 → G1 → R2. If B1 finishes while B2 runs, dispatch R1 immediately. An unrelated documentation card with no dependency can run alongside them. Reserve different paths or serialize writes; unrelated work never forms a wave barrier.

Consequential foundations receive early independent review before dependents build on them. Low-risk related tickets can share a review group with explicit coverage. Every integration gets final review and named project checks, even when checkpoint reports are green.

## Findings and interruption

Check each finding against source and actively try to refute it. Confirmed implementation defects return to builder with exact artifact, scenario and scope. Spec contradictions or missing user decisions return to design; task/dependency flaws return to planning, then red team when substantial. Do not ask builders to implement contradictory requirements. Invalidate and rerun affected reviews/gates after changes.

On interruption or lease loss, stop dispatch and continuation. Late reports remain historical and cannot advance the run. Resume only on an explicit request, after checking artifacts and live worker state. Explicit autonomy needs a ledger, named limits for passes/stalls, completion criteria and authorization boundaries. Ordinary continuation does not create an unattended loop. Session hooks inject context; Stop hooks never imply default continuation.

## Executable review and audit policy

Use the portable CLI `route` for inspected request facts, `review-groups` for returned builder cards, and `audit-policy` for conformance facts. The canonical lane graph is config/flow.json. These rubrics check structure and supplied facts; they do not understand arbitrary prompts or grant authority.

Group micro-tickets by the same outcome and integration point. Set `outcome` or `review_group` on cards before dispatch. Shared-input fallback is only a suggestion: inspect cohesion and review context size. Isolate consequential foundations when dependent work needs their result; do not create one reviewer per small ticket by habit. A final reviewer always inspects the integrated candidate.

Run one auditor instance per needed axis on the frozen candidate, before release. A substantial approved spec triggers spec conformance; substantial binding standards trigger standards conformance; ledger claims trigger ledger conformance. Explicit user-requested axes also run. An unrelated wave finishing does not trigger an audit. Separate reports keep obligations visible. Final code review may run alongside these audits and gates when all inspect the same unchanged artifact.

For execution mechanics, read references/cli.md or use `scripts/orchestra.py --help` from the plugin root. Read the relevant CLI schema before writing cards or review reports. Use JSON review reports bound to `artifact`, with explicit covered task IDs, categories, verdict, findings and summary.
