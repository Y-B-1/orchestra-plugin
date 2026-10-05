# Model matrix

Source of truth: `plugins/orchestra/config/models.json`. This page describes it. Only claude-opus-5-5 and claude-sonnet-5-5 are used. Parallel work never raises effort.

## Claude

| Role / mode | Model | Effort | Native file |
| --- | --- | --- | --- |
| orchestrator (main) | user's selection | user's selection | `orchestrator.md`, with no `model:` or `effort:` line |
| investigator docs (default) | claude-sonnet-5-5 | medium | `investigator.md` |
| investigator code | claude-sonnet-5-5 | low | `investigator-code.md` |
| designer-planner (design, plan, product) | claude-opus-5-5 | high | `designer-planner.md` |
| critic (all modes) | claude-opus-5-5 | high | `critic.md` |
| builder: implementation, frontend, sensitive, mechanical, cleanup | claude-sonnet-5-5 | medium | `builder.md` |
| builder repair | claude-opus-5-5 | medium | none; round 4 only, by dispatch-time model override (`"dispatch": "override"`); rounds 1 to 3 use the builder default (Sonnet medium) |
| code-reviewer final | claude-opus-5-5 | high | `code-reviewer.md` |
| code-reviewer checkpoint | claude-opus-5-5 | medium | `code-reviewer-checkpoint.md` |
| code-reviewer standards lens | claude-sonnet-5-5 | medium | `code-reviewer-standards.md` |
| operator (gate, cleanup, release) | claude-sonnet-5-5 | medium | `operator.md` |

The orchestrator row is the user's selection: the model and effort picked in the client, never pinned by the plugin (`"selection": "user"`). Builder `cleanup` equals the builder default, so it adds no file. Builder `repair` has no variant file; the coordinator passes `claude-opus-5-5` at dispatch, and only after an independent review returned checked coding findings.

## Tool restrictions

The read-only roles are investigator, critic and code-reviewer, including their variants; they disallow `Agent, Edit, Write, NotebookEdit`, and every other worker disallows `Agent`. See docs/roles.md.

## Notes

Each worker agent file pins both model and reasoning effort. Hold settings constant during an assignment. Repair requires an independent review with checked coding findings tied to the earlier builder card. No effort above high or million-token opt-in is generated. Check the active host catalog and account before dispatch; a model name does not establish account availability or a context limit. Unavailable models need an explicit equivalent selection.

## v1 to v2 model mapping

| v1 role | v2 role | Model change |
| --- | --- | --- |
| founder-mind, red-teamer, auditor | designer-planner, critic | none (Opus high) |
| builder-repair | builder repair | dispatch override, no file |
| gatekeeper, releaser | operator gate, release | none (Sonnet medium) |
| janitor | operator cleanup | none |

## Fast mode

Fast is a service-speed setting, separate from reasoning effort. The agent files deliberately omit it so they inherit the parent configuration. Changing the main composer after workers start does not establish that existing worker sessions change too.

For uniform speed, finish or stop current workers, change Fast in the main client, then start the next set. Never report an inferred speed as observed. Orchestra does not change the user's global configuration.
