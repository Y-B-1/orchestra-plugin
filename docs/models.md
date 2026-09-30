# Native model matrix

The Codex matrix uses only GPT-6.1 Sol and GPT-6 Luna. Sol uses high for broad judgment and checked repair; parallel work never raises effort. Main-session model choice remains with the user.

| Contract | Codex model | Effort |
| --- | --- | --- |
| Main, founder, designer-planner, auditor | gpt-6.1-sol | high |
| Final integration code reviewer | gpt-6.1-sol | high |
| Checkpoint code reviewer | gpt-6.1-sol | medium |
| Red team | gpt-6.1-sol | high |
| Builder first attempt: implementation, frontend, sensitive, mechanical | gpt-6.1-sol | medium |
| Builder repair after checked coding findings | gpt-6.1-sol | high |
| Investigator: bounded code discovery | gpt-6-luna | high |
| Investigator: documentation | gpt-6.1-sol | medium |
| Gatekeeper, releaser | gpt-6.1-sol | medium |
| Janitor: read-only hygiene proposal | gpt-6-luna | high |

Claude uses claude-opus-5-5 for judgment at high, checkpoint and repair at medium; claude-sonnet-5-5 for first builds and operations at medium, code discovery at low. Check provider availability before dispatch; unavailable models need an explicit equivalent selection, never silent cross-provider substitution.

Luna receives explicit paths and a bounded read-only question. It returns source evidence or a cleanup proposal; the coordinator checks evidence before edits or removal. Keep external research, implementation, independent approval, command gates and release on Sol. If discovery becomes ambiguous or crosses architecture/permission boundaries, return the unresolved question to the coordinator for a new Sol assignment.

Luna high is a practical starting choice, not a proved optimum for these roles. Published evaluations show capable high-effort workflow performance, but do not establish that xhigh improves Orchestra discovery or hygiene. Token rates remain fixed across effort levels; more reasoning tokens can increase total API cost and latency. API pricing does not directly measure a Codex subscription allowance. See RESEARCH.md for current sources and limits.

Each native worker profile pins both model and reasoning effort. Hold settings constant during an assignment. Repair requires a BLOCKED independent review tied to the earlier builder card. Repair escalates Sol from medium to high. No Astra, effort above high, Cursor fallback or million-token opt-in is generated. Check the active host catalog and account before dispatch; a model name does not establish account availability or a context limit.

## Fast mode

Fast is a service-speed setting, separate from reasoning effort. The profiles deliberately omit `service_tier` so they inherit the parent configuration. Fast maps to the request value `priority`. Changing the main composer after workers start does not establish that existing worker sessions change too.

For uniform speed, finish or stop current workers, select Fast on or off in the main client, then start the next set. The coordinator reports the configured parent setting and whether profiles override it; effective provider speed remains unknown unless the host exposes request metadata. Never report an inferred speed as observed. Orchestra does not change the user's global configuration or transport settings.

Primary references: [custom-agent inheritance](https://developers.openai.com/codex/multi-agent#custom-agents), [service tier configuration](https://learn.chatgpt.com/docs/config-file/config-reference#configtoml).
