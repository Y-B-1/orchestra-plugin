Sentinel: orchestra/references/audit-axes.md

# Conformance axes

Run one critic card per needed axis on the frozen candidate, before release. Each axis reports separately so every obligation stays visible. A report is semantic judgment, not machine proof. Judge the facts yourself; no command decides which axes apply.

| Axis | Run when | Critic mode |
| --- | --- | --- |
| spec | A substantial approved spec exists | `spec` |
| standards | Substantial binding standards apply | `standards` |
| ledger | The run claims completion, approvals or gates | `ledger` |
| surface | By judgment: a shipped surface changed (command, API, UI, docs a user reads) | `surface` |

What each critic checks lives in the matching mode file of the orchestra-critique skill.

An explicit user-requested axis always runs. An unrelated card finishing triggers no audit. The code review and the gates may run beside the axis cards when all read the same unchanged artifact.
