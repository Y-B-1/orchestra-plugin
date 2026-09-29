# Native model matrix

The matrix remains the approved task-based selection. Parallel work never raises effort. Main-session model choice remains with the user.

| Contract | Codex model | Effort |
| --- | --- | --- |
| Main, founder, designer-planner, red team, auditor | gpt-6-astra | high |
| Final integration code reviewer | gpt-6-astra | high |
| Checkpoint code reviewer | gpt-6-astra | medium |
| Builder first attempt: implementation, frontend, sensitive, mechanical | gpt-6.1-sol | medium |
| Builder repair after checked coding findings | gpt-6-astra | medium |
| Investigator: code | gpt-6.1-sol | low |
| Investigator: documentation | gpt-6.1-sol | medium |
| Gatekeeper, janitor, releaser | gpt-6.1-sol | medium |

Claude uses claude-opus-5-5 for judgment at high, checkpoint and repair at medium; claude-sonnet-5 for first builds and operations at medium, code discovery at low. Check provider availability before dispatch; unavailable models need an explicit equivalent selection, never silent cross-provider substitution.

Each native worker profile pins both model and reasoning effort. Hold settings constant during an assignment. Repair requires a BLOCKED independent review tied to the earlier builder card. No first-attempt frontier builder, effort above high, Cursor fallback or million-token opt-in is generated. The observed Codex catalog lists 272,000 context tokens for both models; a future host catalog can change that value.

## Fast mode

Fast is a service-speed setting, separate from reasoning effort. The profiles deliberately omit `service_tier` so they inherit the parent configuration. Fast maps to the request value `priority`. Changing the main composer after workers start does not establish that existing worker sessions change too.

For uniform speed, finish or stop current workers, select Fast on or off in the main client, then start the next set. The coordinator reports the configured parent setting and whether profiles override it; effective provider speed remains unknown unless the host exposes request metadata. Never report an inferred speed as observed. Orchestra does not change the user's global configuration or transport settings.

Primary references: [custom-agent inheritance](https://developers.openai.com/codex/multi-agent#custom-agents), [service tier configuration](https://learn.chatgpt.com/docs/config-file/config-reference#configtoml).
