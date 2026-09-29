# Portable roles and model contracts

The main orchestrator plus ten worker roles use config/roles.json as their canonical contract. config/models.json names provider-native defaults and mode presets. Native assets are generated; do not edit profiles directly. Each prompt names its method, and each worker reads the brief contract plus only the assigned phase method.

| Role | Modes | Responsibility |
| --- | --- | --- |
| orchestrator | main | State, routing, reservations, continuous ready dispatch, integration |
| investigator | code / docs | Source facts or current primary-source research |
| founder-mind | design / audit | Depth ladder, references, actual-user simulation, shipped surfaces |
| designer-planner | design / plan | Separate spec decisions and dependency-aware tickets |
| red-teamer | requirements / feasibility / scope / judge | Independent counterexamples and premise checks |
| builder | implementation / frontend / sensitive / mechanical / repair | Bounded edits; checked-finding repair only |
| code-reviewer | checkpoint / final | Exact diff; inclusive final categories always apply |
| auditor | spec / standards / ledger | Separate conformance axis |
| gatekeeper | checks | Actual command exits and artifact binding |
| janitor | hygiene | Preservation and cleanup proposal |
| releaser | release | Configured authorized commands, exact target and current evidence |

Codex uses gpt-6-astra high for judgment, medium for checkpoint review and checked repair. gpt-6.1-sol medium handles first implementation, operations and docs research; code discovery uses low. Claude uses claude-opus-5-5 high for judgment, medium for checkpoint and checked repair; claude-sonnet-5 medium handles implementation, operations and docs research, low for code discovery. These Claude pins reflect the compared native agent configuration; client availability still needs a live check. Do not silently substitute a different provider's model. The main session model remains the user's choice: the matrix is a recommendation, not a mechanism to override it. Parallel work never raises effort. Settings stay fixed for an assignment.

Workers do not fan out, mutate coordinator state or acquire release permission through their role name. Releaser authority comes only from configured project authorization and an explicit bounded assignment. A CLEAN review adds no permission. Installer receipts and enabled/trusted native hooks govern profile discovery and session context; skill installation alone cannot guarantee either.

Read the progressive procedures in plugins/orchestra/skills/orchestra/SKILL.md. Dispatch briefs carry applicable project/path rules inline and selected method paths. Final review covers requirements, correctness, security, tests, architecture, standards and cleanup, including concrete reuse, simplification, efficiency and layer-placement checks. Auditor reports remain separate from code-diff review. Confirmed code findings route to checked builder repair; contradictory requirements route to design; dependency and acceptance flaws route to planning.
