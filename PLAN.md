# Build plan

| Ticket | Owner | Paths | Done contract |
| --- | --- | --- | --- |
| T1 strict engine | engine worker | scripts/orchestra_core/engine.py, tests/test_engine.py | State, artifacts, cards, ownership, reviews, gates, lifecycle rejection tests pass |
| T2 hooks/guards | hooks worker | scripts/orchestra_core/guards.py, scripts/orchestra_core/hooks.py, tests/test_hooks.py | Native outputs, bounded command parsing, patches, activation/interrupt cases pass |
| T3 contracts | instructions worker | config/roles.json, config/models.json, skills/orchestra/**, docs/roles.md | Approved roles/modes and progressive procedures are complete and internally consistent |
| T4 native package | coordinator | manifests, catalogs, CLI, generator, profile installer, release builder, packaging tests | Both manifests checked, drift clean, safe lifecycle and archive tests pass |
| T5 end-to-end | coordinator + independent review | docs/source-parity.md, tests/test_integration.py, docs/VALIDATION.md | Isolated run, native smoke, source comparison and whole-diff review pass at named commit |

T1/T2/T3 run concurrently in separate worktrees. T4 begins with independent scaffolding and joins their stable interfaces. T5 depends on all implementation. New checked findings route to a repair worker at gpt-6-astra medium. Root owns integration and all public actions; no writer touches the source application. Check all acceptance criteria before claiming release.
