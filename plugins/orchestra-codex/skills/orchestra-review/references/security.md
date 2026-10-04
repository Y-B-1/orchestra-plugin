Source: derived from garrytan/gstack@4015c2870b06 cso/SKILL.md cso/sections/audit-phases.md review/specialists/security.md (MIT); ideas: Claude Code security-review (idea level); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/security.md

# Code reviewer: security lens

Report exploitable problems in the diff only. Report fixes as findings. Do not edit code.

## Model first

Write a short application model before you read hunks: actors, assets, entrypoints, tenant boundaries and invariants. It decides what is reachable.

## Attack surface

Map the attack surface from the entrypoints out.

Census every entrypoint the diff adds or changes: routes, handlers, webhooks, jobs, CLI arguments, file and environment inputs. For each, trace attacker-controlled input to its sink:

- Authentication and authorization, including tenant isolation and object-level access.
- Injection: query, command, template, path traversal and unsafe deserialization.
- Outbound requests the attacker can steer (SSRF) and open redirects.
- Webhooks and APIs: verify signatures over the raw body, and check replay protection.
- Secrets in code, logs, history or CI output. A leaked secret needs rotation. Never rewrite history.
- Personal data in logs, errors, URLs or telemetry, and unsafe defaults.
- Dependencies: a new package counts only if the vulnerable code is reachable.
- CI and release files: `pull_request_target`, script injection through event fields, broad tokens.
- LLM, agent and MCP code: model output reaching a tool, shell or file; prompt content from untrusted sources. Treat a `SKILL.md` as code.
- Spoofing, tampering, repudiation, disclosure, denial of service and privilege escalation: run the six STRIDE questions on each new boundary.

## Precision filter

Report only findings with a reachable path. Apply these exclusions only where an attacker does not control the input: theoretical races, log spoofing, missing hardening with no exploit, denial of service by volume, findings in test-only code. If the attacker controls the input, the exclusion does not apply.

## Report

- Keep severity, confidence and evidence as three separate fields.
- A finding names the entrypoint, the boundary crossed, the impact and the controls you tried to defeat.
- Reachability you cannot establish stays marked unknown.
- Open the summary with coverage: complete, partial or not assessed, per area.
- A scanner the brief requires blocks when absent. An optional scanner that is absent is reported as unavailable.
