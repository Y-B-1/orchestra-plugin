# Native model matrix

Source of truth: `plugins/orchestra/config/models.json`. This page describes it. Claude uses only claude-opus-5-5 and claude-sonnet-5-5. Codex uses only gpt-6.1-sol and gpt-6-luna. Parallel work never raises effort.

## Claude

| Role / mode | Model | Effort | Native file |
| --- | --- | --- | --- |
| orchestrator (main) | user's selection | user's selection | `orchestrator.md`, with no `model:` or `effort:` line |
| investigator docs (default) | claude-sonnet-5-5 | medium | `investigator.md` |
| investigator code | claude-sonnet-5-5 | low | `investigator-code.md` |
| designer-planner (design, plan, product) | claude-opus-5-5 | high | `designer-planner.md` |
| critic (all modes) | claude-opus-5-5 | high | `critic.md` |
| builder: implementation, frontend, sensitive, mechanical, cleanup | claude-sonnet-5-5 | medium | `builder.md` |
| builder repair | claude-opus-5-5 | medium | none; dispatch-time model override (`"dispatch": "override"`) |
| code-reviewer final | claude-opus-5-5 | high | `code-reviewer.md` |
| code-reviewer checkpoint | claude-opus-5-5 | medium | `code-reviewer-checkpoint.md` |
| operator (gate, cleanup, release) | claude-sonnet-5-5 | medium | `operator.md` |

The orchestrator row is the user's selection: the model and effort picked in the client, never pinned by the plugin (`"selection": "user"`). Builder `cleanup` equals the builder default on both harnesses, so it adds no file. Builder `repair` on Claude has no variant file; the coordinator passes `claude-opus-5-5` at dispatch, and only after an independent review returned checked coding findings.

## Codex

| Role / mode | Model | Effort | Native profile |
| --- | --- | --- | --- |
| orchestrator | no profile | n/a | main session model remains the user's choice |
| investigator docs (default) | gpt-6.1-sol | medium | `orchestra_investigator` |
| investigator code | gpt-6-luna | high | `orchestra_investigator_code` |
| designer-planner | gpt-6.1-sol | high | `orchestra_designer_planner` |
| critic (all modes) | gpt-6.1-sol | high | `orchestra_critic` |
| builder: implementation, frontend, sensitive, mechanical, cleanup | gpt-6.1-sol | medium | `orchestra_builder` |
| builder repair | gpt-6.1-sol | high | `orchestra_builder_repair` |
| code-reviewer final | gpt-6.1-sol | high | `orchestra_code_reviewer` |
| code-reviewer checkpoint | gpt-6.1-sol | high | `orchestra_code_reviewer` (same as final; no separate profile) |
| operator gate, release (default) | gpt-6.1-sol | medium | `orchestra_operator` |
| operator cleanup | gpt-6-luna | high | `orchestra_operator_cleanup` |

Result: 9 Claude agent files and 9 Codex profiles. Luna is limited to investigator code discovery and operator cleanup (read-only hygiene proposals). Codex presets always produce a profile when they differ from the default, because a Codex dispatch-time model override is unverified.

## sandbox_mode and tool restrictions

The read-only roles are investigator, critic and code-reviewer, including their variants. Their Codex profiles set `sandbox_mode = "read-only"`; operator and builder profiles set none, so the operator cleanup profile is Luna but not sandboxed by the profile. On Claude the same roles disallow `Agent, Edit, Write, NotebookEdit`, and every other worker disallows `Agent`. See docs/roles.md.

## Notes

Luna receives explicit paths and a bounded read-only question. It returns source evidence or a cleanup proposal; the coordinator checks evidence before edits or removal. Keep external research, implementation, independent approval, command gates and release on Sol. If discovery becomes ambiguous or crosses architecture or permission boundaries, return the unresolved question to the coordinator for a new Sol assignment.

Luna high is a practical starting choice, not a proved optimum. Published evaluations do not establish that xhigh improves Orchestra discovery or hygiene. Token rates stay fixed across effort levels; more reasoning tokens can increase total API cost and latency. See RESEARCH.md for sources and limits.

Each native worker profile pins both model and reasoning effort. Hold settings constant during an assignment. Repair requires an independent review with checked coding findings tied to the earlier builder card. No effort above high, Cursor fallback or million-token opt-in is generated. Check the active host catalog and account before dispatch; a model name does not establish account availability or a context limit. Unavailable models need an explicit equivalent selection, never silent cross-provider substitution.

## v1 to v2 model mapping

| v1 role | v2 role | Model change |
| --- | --- | --- |
| founder-mind, red-teamer, auditor | designer-planner, critic | none (Opus high / Sol high) |
| builder-repair | builder repair | Claude: dispatch override, no file; Codex: profile kept |
| gatekeeper, releaser | operator gate, release | none (Sonnet medium / Sol medium) |
| janitor | operator cleanup | none (Luna high on Codex) |

## Fast mode

Fast is a service-speed setting, separate from reasoning effort. The profiles deliberately omit `service_tier` so they inherit the parent configuration. Fast maps to the request value `priority`. Changing the main composer after workers start does not establish that existing worker sessions change too.

For uniform speed, finish or stop current workers, select Fast on or off in the main client, then start the next set. The coordinator reports the configured parent setting and whether profiles override it; effective provider speed remains unknown unless the host exposes request metadata. Never report an inferred speed as observed. Orchestra does not change the user's global configuration or transport settings.

Primary references: [custom-agent inheritance](https://developers.openai.com/codex/multi-agent#custom-agents), [service tier configuration](https://learn.chatgpt.com/docs/config-file/config-reference#configtoml).
