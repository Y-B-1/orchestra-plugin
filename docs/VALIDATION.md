# Validation evidence — 2026-09-30

## Checked

| Check | Result |
| --- | --- |
| Python 3.11 unit/integration suite | 89 tests pass (1.0.1 refresh) |
| Canonical native profile drift | 27 generated files match: 13 Codex, 14 Claude |
| Skill Creator frontmatter check | Pass |
| Claude plugin manifest, strict | Pass, no warnings |
| Claude marketplace manifest, strict | Pass, no warnings |
| Codex marketplace add/install/list/remove, isolated CODEX_HOME | All exit 0; correct plugin ID/version discovered |
| Bundled Codex CLI 0.159.0 model smoke, isolated configuration | Sol medium returns the requested response, exit 0 |
| Native named custom worker round trip, Codex CLI 0.159.0 | Sol medium delegates to installed orchestra_investigator_code; Luna high returns the correct fixture finding, exit 0; session records show both model/effort settings |
| Claude marketplace add/install/list/uninstall/remove, isolated configuration | All exit 0; correct plugin ID/version discovered |
| User profile install/update/uninstall | Pass; unrelated files preserved; collisions and symlinked locations rejected |
| Paths with spaces | Native installation, hooks and local release pass |
| Real local release | Structured CLI pushed only a disposable bare Git target; remote full HEAD matched the candidate |
| Dirty/stale evidence rejection | Pass; changed reports/logs, wrong metadata, incomplete coverage and invalidated artifacts reject |
| Autonomous continuation | Explicit intact ledger only; pass/stall caps and interrupt rejection pass |
| Independent skill forward-test | Produced conditional design/plan, concurrent ownership, one outcome review group and explicit audit decisions; fixture sources unchanged |
| Source comparison | All 31 source flow states and all 14 source responsibilities mapped |
| Independent final code review and spec/parity audit | Both CLEAN at a82d3e01859193ea2b85fc54c7cff6d7accdde4e; no unresolved blocking findings |
| Application source preservation | Original HEAD remained fd140bd32df441db36b1f70bd2d506a8582958f9; working tree remained clean |

The suite includes actual subprocess commands, locking/concurrency, schema rejection, release receipts, and repeat-run history. Final-audit regressions cover newer BLOCKED review precedence, repair chains, reported-work review scheduling, terminal release cards, actor/lease rejection, plugin state-path protection, release destinations, literal shell wrappers and process timeouts. The local release fixture has no production remote, deployment or credentials.

## Native limits observed

Codex CLI 0.158.0 accepted native packaging and installation but rejected an authenticated gpt-6.1-sol request with HTTP 400. The desktop-bundled CLI 0.159.0 subsequently ran that model at medium successfully using isolated configuration. Use a current compatible client; metadata installation alone does not prove account/model availability. The 2026-09-30 matrix uses only Sol and Luna; red team/checked repair use Sol high and bounded discovery/hygiene use Luna high.

The first native custom-worker check timed out at 55 seconds after loading Luna high. A second check allowed 150 seconds and completed successfully: the named worker read one fixture file and returned the correct cited finding. Native turn records show Sol medium and Luna high. This proves profile discovery and that bounded round trip; it is not a benchmark, a successful Claude model session or proof of trusted startup hooks. Temporary authentication copies were removed; global credentials were unchanged.

Claude Code 2.1.284 accepted packaging and installation. A live print-mode attempt failed before model execution because its OAuth session expired and could not refresh. Authentication needs renewal before live model testing. No login or global credential change was performed.

Hook adapters were exercised with native-shaped payloads and real package entrypoints, including allowed/denied directions. Persisted native hook trust was neither written nor bypassed. Trusted automatic startup in a user's normal session remains a user trust check, not an established smoke-test result.

Claude's validator accepts manifest JSON paths and supported directories. Passing an individual agent Markdown path makes that command parse the file as JSON; those exploratory invocations failed for command-shape reasons and do not validate agent content. Directory invocations returned no component records. Canonical references, model settings, generated TOML and worker contracts were checked separately; do not mistake an empty validator result for a semantic agent test.

Other harness adapters, native Windows, production releases and deployed-system checks are outside this validation. GitHub distribution is separate from universal public-directory approval. Shell guards do not interpret arbitrary scripts, stdin, aliases or authenticate worker identities.

Final independent review and the checked candidate hash are recorded in BUILD-LEDGER.md. Native authentication or trust limitations do not become green evidence.

## 1.0.1 refresh

Inline assignments share worker ownership, dependency, capacity, lease and independent review checks. Codex uses only Sol/Luna; checked repair and red team use Sol high.

Native Codex 0.159.0 hook discovery reproduced zero Orchestra hooks with the portable root manifest. Its native compatibility-only package returns all five events exactly once as untrusted. The Codex catalog now selects a generated copy of the canonical runtime that omits only unsupported/Claude packaging files. The canonical portable manifest remains schema-valid; Claude keeps its separate definition. The generator and parity test check every copied byte. No trust record changed.
