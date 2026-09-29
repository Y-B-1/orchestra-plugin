# Build ledger

Status: FINAL REVIEW. Ten worker contracts plus main, native matrices and GitHub distribution are approved. No production target or classifier service is configured. The application reference stayed read-only.

| Ticket | State | Evidence |
| --- | --- | --- |
| T1 | BUILT | Engine, card/evidence/lease tests and completion checks |
| T2 | BUILT | Shared parser and native hooks; covered malformed and release cases |
| T3 | BUILT | Progressive skill, all roles/modes, canonical native matrices |
| T4 | BUILT | Both native installs/removals exit 0; safe profiles; reproducible archives |
| T5 | REVIEW | 56 tests pass, local bare-target release matches full HEAD, independent skill forward-test complete |

Candidate implementation: c92bd08462cea3d73504a60a11c625553f742200. Final code review and spec audit are pending. Subsequent commits need current gate evidence.

Live native model limits: standalone Codex account rejected the approved Sol model; Claude OAuth expired. Native metadata installation succeeds, but those model sessions did not. Native hook trust was not written or bypassed. User review/trust and compatible authenticated model access remain separate activation checks. See VALIDATION.md.
