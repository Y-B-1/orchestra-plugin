# Validation evidence — 2026-09-30

## Checked

| Check | Result |
| --- | --- |
| Python 3.11 unit/integration suite | 56 tests pass |
| Canonical native profile drift | 27 generated files match: 13 Codex, 14 Claude |
| Skill Creator frontmatter check | Pass |
| Claude plugin manifest, strict | Pass, no warnings |
| Claude marketplace manifest, strict | Pass, no warnings |
| Codex marketplace add/install/list/remove, isolated CODEX_HOME | All exit 0; correct plugin ID/version discovered |
| Claude marketplace add/install/list/uninstall/remove, isolated configuration | All exit 0; correct plugin ID/version discovered |
| User profile install/update/uninstall | Pass; unrelated files preserved; collisions and symlinked locations rejected |
| Paths with spaces | Native installation, hooks and local release pass |
| Real local release | Structured CLI pushed only a disposable bare Git target; remote full HEAD matched the candidate |
| Dirty/stale evidence rejection | Pass; changed reports/logs, wrong metadata, incomplete coverage and invalidated artifacts reject |
| Autonomous continuation | Explicit intact ledger only; pass/stall caps and interrupt rejection pass |
| Independent skill forward-test | Produced conditional design/plan, concurrent ownership, one outcome review group and explicit audit decisions; fixture sources unchanged |
| Source comparison | All 31 source flow states and all 14 source responsibilities mapped |
| Application source preservation | Original HEAD remained fd140bd32df441db36b1f70bd2d506a8582958f9; working tree remained clean |

The suite includes actual subprocess commands, locking/concurrency, schema rejection, release receipts, and repeat-run history. The local release fixture has no production remote, deployment or credentials.

## Native limits observed

Codex CLI 0.158.0 accepted native packaging and installation. Its authenticated standalone model request rejected gpt-6.1-sol with HTTP 400: model is not supported when using Codex with a ChatGPT account. The current desktop host exposes the approved matrix to its agent tool, but that does not establish availability for every separate client/account. Matrix defaults remain unchanged by user instruction. Actual native worker/model execution in the standalone CLI is not a passing check.

Claude Code 2.1.284 accepted packaging and installation. A live print-mode attempt failed before model execution because its OAuth session expired and could not refresh. Authentication needs renewal before live model testing. No login or global credential change was performed.

Hook adapters were exercised with native-shaped payloads and real package entrypoints, including allowed/denied directions. Persisted native hook trust was neither written nor bypassed. Trusted automatic startup in a user's normal session remains a user trust check, not an established smoke-test result.

Claude's validator accepts manifest JSON paths and supported directories. Passing an individual agent Markdown path makes that command parse the file as JSON; those exploratory invocations failed for command-shape reasons and do not validate agent content. Directory invocations returned no component records. Canonical references, model settings, generated TOML and worker contracts were checked separately; do not mistake an empty validator result for a semantic agent test.

Other harness adapters, native Windows, production releases and deployed-system checks are outside this validation. GitHub distribution is separate from universal public-directory approval. Shell guards do not interpret arbitrary scripts, stdin, aliases or authenticate worker identities.

Final independent review and the checked candidate hash are recorded in BUILD-LEDGER.md. Native authentication or trust limitations do not become green evidence.
