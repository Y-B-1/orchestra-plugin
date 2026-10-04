# Build ledger

Status: CHECKED. Ten worker contracts plus main, native matrices and GitHub distribution are approved. No production target or classifier service is configured. The application reference stayed read-only.

| Ticket | State | Evidence |
| --- | --- | --- |
| T1 | BUILT | Engine, card/evidence/lease tests and completion checks |
| T2 | BUILT | Shared parser and native hooks; covered malformed and release cases |
| T3 | BUILT | Progressive skill, all roles/modes, canonical native matrices |
| T4 | BUILT | Both native installs/removals exit 0; safe profiles; reproducible archives |
| T5 | CHECKED | 84 tests pass; code review and spec audit CLEAN; local bare-target release matches full HEAD; skill forward-test complete |

Implementation candidate a82d3e01859193ea2b85fc54c7cff6d7accdde4e received independent Sol code-review and spec-audit CLEAN verdicts. The root ran all 84 tests at that candidate, exit 0. Earlier findings received regression-backed repairs for review integrity, repair scheduling, leases, state paths, command parsing and exact Git source/context binding. Known Git releases now use a finite direct four-argument recipe.

Final release metadata needs a documentation-delta check and renewed gates. The GitHub release records the exact published commit and archive checksums. Native hook trust remains a user activation check, not a waived gate.

Native model evidence: older Codex CLI 0.158.0 rejected Sol, while desktop-bundled 0.159.0 ran Sol medium and a named Luna-high discovery worker successfully. Claude OAuth expired. Native metadata installation succeeds for both clients. Native hook trust was not written or bypassed. User hook review/trust remains a separate activation check. See VALIDATION.md.

## 1.0.1 update — 2026-09-30

The update removes Astra from Codex routing, adds reserved inline assignments beside disjoint workers, and fixes native hook discovery. Codex 0.159.0 selects the generated compatibility package; the canonical portable manifest and Claude package stay separate. All 44 native package bytes and 27 profiles match generation. The suite passes 89 tests; native isolated hook listing returns five untrusted definitions exactly once. Final artifact review and publication receipts follow these checks. No hook trust is written.

## 2.0.0 build — 2026-10-04

Tracked here, not in the v1 engine (PLAN-v2 0.1). Integration is serial: merge, checkpoint review on the merged commit, accept (PLAN-v2 0.3). Worktrees live under the session scratchpad (`$SCRATCH/wt/<ticket>`).

| Card | Owner | Worktree | Merged commit | Review verdict | Acceptance |
| --- | --- | --- | --- | --- | --- |
| I1 | investigator | none | 512bfac (RESEARCH-v2) | coordinator check | ACCEPTED |
| I2 | investigator | none | 512bfac (RESEARCH-v2 I2) | coordinator re-check of SHAs and licenses | ACCEPTED |
| P0 r1 | critic feasibility + scope | none | e9140d0 (round 5 repair) | ISSUES FF1-FF3, SF1-SF10, routed to designer-planner | REPAIRED |
| P0 r2 | critic feasibility + scope | none | 3e0889d (round 6 repair) | ISSUES F1-F5, N1-N4 (planning only); all FF/SF RESOLVED | REPAIRED; P0 accepted for B1 scope |
| MX | investigator (matrix) | main checkout (one-time exception, PLAN round 6) | 6003c11 | coordinator check: one path, no personal paths | REPAIRING (MXR r1 ISSUES, 8 content findings; routed to MX-r1) |
| B1 | builder | $SCRATCH/wt/B1 | 2c515f5 (425758e, 31ef9b2, 25bf9da coordinator fix: host-written tsconfig.json excluded and gitignored, scope extension) | R1 CLEAN; SPEC 10.2 fallback used (validator rejects `typeof $.x`; load-time validation instead) | ACCEPTED; live steps pending (heartbeat advance, interactive /exit, one SessionStart context); release build rerun owed to G1 |
| R1 F1 | design gap | none | n/a | session.end on /clear or resume stops the tick; new id never gets a marker | ROUTED to designer-planner before B5; R1 F2-F4 folded into B5 |
