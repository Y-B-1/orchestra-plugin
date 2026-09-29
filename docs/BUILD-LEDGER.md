# Build ledger

Status: FINAL REVIEW. Ten worker contracts plus main, native matrices and GitHub distribution are approved. No production target or classifier service is configured. The application reference stayed read-only.

| Ticket | State | Evidence |
| --- | --- | --- |
| T1 | BUILT | Engine, card/evidence/lease tests and completion checks |
| T2 | BUILT | Shared parser and native hooks; covered malformed and release cases |
| T3 | BUILT | Progressive skill, all roles/modes, canonical native matrices |
| T4 | BUILT | Both native installs/removals exit 0; safe profiles; reproducible archives |
| T5 | REVIEW | 82 tests pass, local bare-target release matches full HEAD, independent skill forward-test complete |

The initial final review found review-verdict, repair scheduling, release-lease, state-path and literal-command gaps. Checked repair commits address those failures with regression tests. A second Sol review found unchecked push sources, altered governing review evidence and grouped-wrapper gaps. Checked repair commits fix those cases with regressions. Fresh Sol final code review and spec audit remain pending on the integrated candidate. Subsequent commits need current gate evidence.

Native model evidence: older Codex CLI 0.158.0 rejected Sol, while desktop-bundled 0.159.0 ran Sol medium and a named Luna-high discovery worker successfully. Claude OAuth expired. Native metadata installation succeeds for both clients. Native hook trust was not written or bypassed. User hook review/trust remains a separate activation check. See VALIDATION.md.
