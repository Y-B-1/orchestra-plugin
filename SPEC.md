# Orchestra 1.0 specification

## Approved outcome

One installable plugin source for Codex and Claude Code, with a reusable core for other harnesses. An enabled, trusted plugin gives the main session the coordinator contract. Opening a session injects context only: no repository repair, automatic resume or unrequested autonomous loop.

## Roles

Main orchestrator plus ten workers: investigator, founder-mind, designer-planner, red-teamer, builder, code-reviewer, auditor, gatekeeper, janitor, releaser. Investigator has code/docs modes; designer-planner has design/plan modes; builder has implementation/frontend/sensitive/mechanical/repair presets; code-reviewer has checkpoint/final modes; auditor has spec/standards/ledger modes. Founder-mind preserves product depth, researched references, user simulation and shipped-surface audit. All workers return evidence and never own coordinator state or fan-out.

Codex model matrix: main, founder, designer-planner, final reviewer and auditor gpt-6.1-sol high; checkpoint reviewer, first builder, gatekeeper, releaser and docs investigator gpt-6.1-sol medium; code discovery and janitor gpt-6-luna high; red team and checked builder repair gpt-6.1-sol high. Only Sol and Luna run in Codex. Claude uses its own native matrix. No cross-provider model names, Luna builds or parallel-effort inflation. Main model remains a user choice.

## Routing and scheduling

Route each item by readiness, uncertainty, dependencies and consequences. Lanes: answer, investigate, direct, design, plan, bug, review, full-test. Direct work still needs a goal, bounded ownership and acceptance criteria. Bugs need diagnosis before repair. Substantial plans need independent red-team evidence. Formal planning produces tasks, dependencies, exclusive files/resources and acceptance checks.

The strict core stores role-column cards and queued/running/reported/repairing/accepted states. Detect cycles, unknown dependencies, owner/resource collisions, unavailable role/mode, missing input/acceptance criteria and capacity exhaustion. Dispatch ready independent work continuously; completion of unrelated work is not a barrier. Read-only review cards use review_of for reported work, avoiding an acceptance deadlock. Checked repair transfers ownership through the repair chain. A separate worker reviews the exact artifact; review groups can combine low-risk tickets, but consequential foundations need early review. Always review final integration and all final categories: requirements, correctness, security, tests, architecture, standards, cleanup.

## Evidence and lifecycle

Bind evidence to repository identity, full commit, dirty-tree fingerprint, policy revision and requested action. Gates run argv commands and record actual exits/log hashes; compare the artifact before and after. Reject self-review, empty reports, altered reports/logs, stale evidence, wrong repositories/targets and failed required checks. Reviews remain semantic judgments, not machine-proven correctness. No arbitrary pass stamp CLI.

Keep run data outside the immutable package and application. Atomic locked updates prevent concurrent lost writes. Main owns a session lease; interrupted runs stop dispatch/continuation and late completion cannot advance state. Explicit autonomy has a ledger and bounded passes/stalls; no default Stop continuation. Cleanup examines owned directories, dirty bytes and live processes; preserve work on a named branch before removal. Tracked memory edits happen before final gates.

## Enforcement boundary

Use one bounded Git/shell classifier for known destructive actions, wholesale staging/stash and provider release commands. PreToolUse rejects covered invalid actions and malformed payloads. Worker profiles restrict delegation and relevant capabilities; docs/browser/state-read are usable. Interception of arbitrary interpreters, script contents, aliases, stdin or missing native identity is best effort. Structured execution independently checks actions. Hook trust is never auto-written or bypassed in normal installation. Plugin installation alone does not register undocumented Codex agents; use receipt-owned namespaced user profiles and safe uninstall.

Release stays disabled until a project config names authorization, exact remote/target, checks and commands. Review does not grant new permission. No project-specific ports, database writes, deployment commands, relays, automatic rollback or charter symlinks in portable defaults. Missing optional scanners report unavailable; required scanners block.

## Package and acceptance

Portable root manifest plus native OpenAI/Claude overlays and separate hook files. Shared progressive skill and canonical role/matrix definitions generate native profiles. GitHub distribution uses a clean history, MIT license for original package code and explicit source comparison documentation without private snapshots. No remote service/API key is needed. Support Python 3.11+, Git and each named native client version actually checked.

Required proof: unit/integration tests, malformed and stale cases, path-with-spaces, generated asset drift, native manifest checks, isolated role/profile and hook smoke, source parity mapping, independent final audit, clean install/uninstall receipts and release archive checksums. Native trust/discovery limits and unperformed live checks are reported honestly.
