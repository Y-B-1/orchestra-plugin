# Build ledger

Status: ACTIVE. User approved ten roles and authorized complete implementation and GitHub distribution. The final audit runs before implementation. No classifier API or production target is needed.

| Ticket | State | Evidence |
| --- | --- | --- |
| T1 | READY | Engine acceptance tests defined in PLAN |
| T2 | READY | Prior source probes identify parser/identity gaps; replacement required |
| T3 | READY | Final role table and current native matrix approved |
| T4 | READY | Installed client help and primary docs checked |
| T5 | WAITING | Depends on the integrated package |

Known constraints: Codex hook trust needs native review; startup injection is not proof of semantic compliance. Codex child identity and unrestricted shell effects cannot be fully authenticated by plugin hooks. Installer must preserve unrelated configuration and work. Native runtime smokes use disposable projects only.
