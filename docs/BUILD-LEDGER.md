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
