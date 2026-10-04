Sentinel: orchestra/references/coordination.md
Stub: B4 skeleton; ticket S1 rewrites this file and removes this line.

# Main coordinator procedure

Inspect project rules, repository identity, branch and dirty bytes first. Preserve existing work. Split the request into outcomes; size each item, not the whole message. Resolve facts from code before asking for product decisions. Record settled decisions without silently broadening scope.

## Route by readiness and consequence

| Lane | Trigger | Minimum contract |
| --- | --- | --- |
| answer | Self-contained question | Direct answer; no run ceremony |
| investigate | Unknown premise/API/behavior | Investigator code/docs mode; evidence before design |
| direct | Settled, bounded low-risk change | Goal, ownership, acceptance checks, independent review |
| design | Product choice remains | Designer-planner product mode as needed, then design mode; wait for necessary decisions |
| plan | Approved substantial design | Designer-planner plan mode, independent critic challenge |
| bug | Defect | Investigator diagnosis and failing behavior evidence before builder repair |
| review | Existing artifact | Independent code-reviewer; critic for a named conformance axis |
| full-test | Explicit owner request | Operator gate mode with requested full commands; no silent suite expansion |

Lanes are routing choices, not automatic approval. Unknown requirements go to design; dependency mistakes go to planning; checked code defects go to builder. Use first implementation presets until independently checked findings justify repair.

## Choose an executor before acting

For each ready item, choose inline execution by the main session or dispatch to a worker. This choice is separate from its lane. Prefer inline when the main already holds the needed context and the bounded work costs less than a handoff. Prefer workers for independent units, deeper investigation or substantial implementation. Consider risk, uncertainty, available capacity and context cost; file count alone does not decide. State the choice briefly for substantial work. Neither option skips design prerequisites, acceptance checks or independent review.

Main can execute one inline card while disjoint workers run. In an active run, reserve the card with `inline TASK`, then report under the coordinator's real actor identity and returned token. The engine checks the same ownership, resources, dependencies, capacity and lease as worker dispatch. Never edit a worker-owned file inline. Separate independent code-reviewer and critic assignments remain workers; main cannot approve its own implementation. Self-contained answers and tiny reads still need no run.

## Kanban and dependency graph

The board's columns are role assignments, not sequence barriers. Cards contain role/mode, input artifact, dependencies, explicit files/resources and acceptance criteria. Their states are queued, running, reported, repairing, accepted. Reported means work returned; accepted means the coordinator checked evidence and completed required independent review. Ordinary dependent work starts after dependencies are accepted. Review roles instead name reported targets in review_of; never require the reviewed builder's acceptance before its review.

Only running assignments consume capacity, including an inline card. Reported work keeps ownership until acceptance. Read-only review_of cards may inspect their reported targets without taking write ownership; they still reserve their own resources. Repair creation suspends its ancestors as repairing and transfers their reservations to the queued repair. Repair acceptance and fresh independent coverage must precede ancestor acceptance.

Before dispatch, reject unknown or cyclic dependencies, missing inputs/checks, unavailable roles/modes, overlapping ownership/resources and exhausted capacity. Reserve ownership atomically through the structured engine; prose scheduling is not a lock. Track worker identity, activity evidence and session lease. The main alone changes coordinator state and schedules workers.

Example: a settings request produces I1 investigator, D1 design, P1 plan, B1 API builder, B2 UI builder, R1 checkpoint, G1 gates and R2 final review. Accepted dependencies connect I1 → D1 → P1 → B1 and B2. R1 uses review_of: [B1] and can start when B1 reports while B2 runs. After accepted builders, G1 runs checks; R2 inspects the frozen integration. An unrelated documentation card can run alongside them. Reserve different paths or serialize writes; unrelated work never forms a wave barrier.

Consequential foundations receive early independent review before dependents build on them. Low-risk related tickets can share a review group with explicit coverage. Every integration gets final review and named project checks, even when checkpoint reports are green.

## Findings and interruption

Check each finding against source and actively try to refute it. Confirmed implementation defects return to builder with exact artifact, scenario and scope. Spec contradictions or missing user decisions return to design; task/dependency flaws return to planning, then critic challenge when substantial. Do not ask builders to implement contradictory requirements. Invalidate and rerun affected reviews/gates after changes.

On interruption or lease loss, stop dispatch and continuation. Late reports remain historical and cannot advance the run. Resume only on an explicit request, after checking artifacts and live worker state. Explicit autonomy needs a ledger, named limits for passes/stalls, completion criteria and authorization boundaries. Ordinary continuation does not create an unattended loop. Session hooks inject context; Stop hooks never imply default continuation.

## Executable review and audit policy

Use the portable CLI `route` for inspected request facts, `review-groups` for returned builder cards, and `audit-policy` for conformance facts. The canonical lane graph is config/flow.json. These rubrics check structure and supplied facts; they do not understand arbitrary prompts or grant authority.

Group micro-tickets by the same outcome and integration point. Set `outcome` or `review_group` on cards before dispatch. Shared-input fallback is only a suggestion: inspect cohesion and review context size. Isolate consequential foundations when dependent work needs their result; do not create one reviewer per small ticket by habit. A final reviewer always inspects the integrated candidate.

Conformance axes: references/audit-axes.md.

At most one terminal operator release card belongs to a run. Final review covers every pre-release card; the release execution is a later operation. Dispatch that card before requesting a permit. Release checks all pre-release obligations and the active coordinator lease; finish additionally needs the release card's inspected report and acceptance. A later intact BLOCKED verdict supersedes older CLEAN coverage of the same category and artifact.

For execution mechanics, read references/cli.md or use `scripts/orchestra.py --help` from the plugin root. Read the relevant CLI schema before writing cards or review reports. Use JSON review reports bound to `artifact`, with explicit covered task IDs, categories, verdict, findings and summary.
