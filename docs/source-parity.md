# Comparison with the audited Claude Code setup

Reference: the embedded DevOps Orchestra at commit `fd140bd32df441db36b1f70bd2d506a8582958f9`, plus portable Orchestra 0.5.0 at `82fe61fd644bb0d55965be8aa6da0bdee4721784`. Inspection was read-only. Private snapshots, project paths, product state and credentials are excluded from this distribution.

The source contains 14 Claude worker bodies and 31 flow states. The new package preserves responsibilities through six worker roles plus the main (2.0.0; 1.0.1 used ten worker contracts). Count reductions combine equivalent scopes, not independent perspectives.

| Source responsibilities | New contract | Preserved distinction |
| --- | --- | --- |
| scout + researcher | investigator code/docs | Source facts vs current primary-source research |
| founder-mind | designer-planner product; critic surface | Depth ladder, researched references, real-user simulation, shipped quality |
| architect + planner | designer-planner design/plan | Approved design precedes executable ownership and dependency plan |
| red-teamer | critic requirements/feasibility/scope/judge | Independent challenge, no self-approval |
| builder + builder-max + runtime lanes | builder modes | First attempt vs checked-findings repair |
| reviewer + pr-reviewer | code-reviewer checkpoint/final | Foundation/group inspection vs full integration |
| auditor | critic spec/standards/ledger | Separate reports, omissions beyond changed code |
| gatekeeper | operator gate + checked command runner | Actual commands/exits, no fixes or inferred passes |
| janitor | operator cleanup + main lifecycle | Owned hygiene and preservation before removal |
| releaser | operator release + checked release runner | Explicit target authority and live-result inspection |

Domain vocabulary lives in the designer-planner skill and project context. There is no additional domain worker in the 14 inspected source bodies. The generator is deterministic packaging code, not a runtime agent.

## Every source flow state

| Source states | Portable home or deliberate change |
| --- | --- |
| intake | coordinator fact inspection and the triage reference |
| trivial.inline | answer/direct lane, proportionate proof |
| small.design, small.build, small.close | bounded brief, builder group review, checks, close |
| design.recon, design.frontier | investigator and decision rounds |
| design.approaches, design.spec, design.gate | founder/design dossier, settled spec, independent challenge |
| plan.pickup, plan.recon, plan.draft, plan.redteam | approved inputs, ownership graph, red-team findings loop |
| execute.setup, execute.ticket-loop | external run state, reservations, continuous ready scheduling |
| execute.review | reported-card review groups; early consequential foundations |
| execute.integrate, execute.wave-close | coordinator integration; no unrelated wave barrier |
| gates.fast | configured argv runner, logs, actual exit and exact artifact |
| review.pr | inclusive final code review with all categories |
| audit.decide, audit.run | coordinator-chosen axes (audit-axes reference); independent critic per needed axis on frozen candidate |
| release.merge, release.deploy | disabled-by-default exact project-authorized release recipe |
| release.rollback | excluded automatic rollback; needs separate explicit authority |
| fullsuite.run | explicit owner-command full-test lane |
| bug.feedback-loop | diagnosis and failing evidence before scoped repair |
| cleanup.final | run-owned hygiene, named-branch preservation, main removal |
| terminal.done | accepted obligations plus completion evidence |
| autonomy.loop | explicit intact ledger, bounded passes/stalls, interruption wins |

## Hook and instruction changes

The source registers 23 Claude handlers, counting repeated handler entries. The package has five Claude event handlers (SessionStart, SubagentStart, PreToolUse, Stop and SessionEnd). Fewer handlers share one implementation; counts alone do not prove equivalent enforcement.

The 2.0.0 trim removed the three advisory routing, grouping and audit-axis commands; their rules are coordinator prose. Preserved: explicit staging, destructive Git guards, independent review, honest exits, context in worker briefs, no worker fan-out, evidence before release, bounded explicit autonomy, careful cleanup. Strengthened: full hashes, dirty-tree and policy binding, immutable report/log hashes, explicit final task coverage, exact configured commands, malformed input rejection, role/method consistency.

Changed: isolated concurrent writers replace conflicting shared-index rules; micro-tickets share outcome reviews; auditor axes follow concrete gaps rather than fixed wave rituals. Repair escalates after the first checked coding findings, resolving the source's contradictory round-four text. Final review always covers security, reuse, simplification, efficiency and layer placement; a focused lens cannot remove that coverage.

Excluded: startup charter repair, product-specific paths/ports/DB/remote grants, old model switch guards, other-harness orchestration, relays, automatic rollback, stale pipeline assumptions and absent-scanner pass claims. No Charge dependency or copied Charge skill is distributed.

The comparison preserves intent where native mechanics differ. Claude discovers package agents natively. Hooks and caller identifiers are workflow controls, not malicious-agent isolation. Native trust and runtime activation are separate checks.
