# RESEARCH-v2 (I1)

Accessed 2026-10-04 against Claude Code 2.1.289 and codex-cli 0.160.0. Expires with the 2.0.0 release.

## Q1. `skills:` name form, and `disable-model-invocation`
- **Name form: UNKNOWN for same-plugin skills.**
  - DOCUMENTED, https://code.claude.com/docs/en/sub-agents: "Use the `skills` field to inject skill content into a subagent's context at startup." Its example uses bare names (`api-conventions`).
  - The docs say nothing about `plugin:skill` or same-plugin resolution. A fetch of the sub-agents page for any such text found none.
  - OBSERVED: the installed plugin `openai-codex/codex` 1.0.6 has an agent `codex-rescue.md` with `skills: [codex-cli-runtime, gpt-5-4-prompting]`. These are bare names of skills in the same plugin's `skills/` dir. This shows the bare form is used in shipped plugins. I did not observe whether the preload actually resolves at runtime.
  - Plugin agents support `skills` (https://code.claude.com/docs/en/plugins/components, "Supported fields: ... `skills`"). `permissionMode`, `hooks`, `mcpServers` and `initialPrompt` are ignored.
- **`disable-model-invocation: true` blocks preload: DOCUMENTED.**
  - "You can't preload skills that set `disable-model-invocation: true`, since preloading draws from the same set of skills Claude can invoke."
  - A listed skill that is missing or disabled is skipped with only a debug-log warning. So a wrong name fails silently.
- **Consequence for PLAN B4:**
  - Use bare names first.
  - The live B4 check must read the debug log (`claude --debug`) for "skipped" warnings. A worker that merely runs is not proof.
  - The B4 fallback applies if the bare form does not preload.
  - Role skills must not set `disable-model-invocation`.

## Q2. Agent tool `model` parameter: DOCUMENTED
From https://code.claude.com/docs/en/sub-agents: "Full model ID: use a full model ID such as `claude-opus-5-5` or `claude-sonnet-5`. Accepts the same values as the `--model` flag". Aliases are `sonnet`, `opus`, `haiku` and `fable`, plus `inherit`. "The per-invocation `model` parameter accepts the same values."
- `claude-opus-5-5` is accepted. The `opus` alias fallback is also valid.
- UNKNOWN: whether the Agent tool in this build rejects an unlisted id at call time. Not observed.

## Q3. Codex read-only profile key: DOCUMENTED (https://learn.chatgpt.com/docs/config-file/config-reference, reached through a 308 redirect from developers.openai.com)
- The key is `sandbox_mode`, with values `"read-only"`, `"workspace-write"` and `"danger-full-access"`.
- Agent roles are declared as `agents.<name>.config_file` ("Path to a TOML config layer for that role"). "Role configuration files support `sandbox_mode` and `model`".
- So `sandbox_mode = "read-only"` in a role file is documented to apply.
- OBSERVED: the installed role files (`~/.codex/agents/orchestra_*.toml`) set `name`, `description`, `model`, `model_reasoning_effort` and `developer_instructions`, and no `sandbox_mode`. `grep sandbox_mode ~/.codex/agents ~/.codex/config.toml` returned nothing.
- The docs also list `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort`.
- UNKNOWN: whether a per-role dispatch-time model override exists. SPEC already treats that as unverified, so keep Codex variants as profiles.

## Q4. Hook payloads
- **SessionEnd `session_id` and `cwd`: DOCUMENTED** (https://code.claude.com/docs/en/hooks).
  - Common fields for every event include `session_id`, `transcript_path` and `cwd`. SessionEnd adds `reason`: `clear`, `resume`, `logout`, `prompt_input_exit` or `other`. Example: `{"session_id":"abc123","cwd":"/Users/my-project","hook_event_name":"SessionEnd","reason":"clear"}`.
  - `cwd` is defined as "Current working directory when the hook is invoked". Equality with the SessionStart `cwd` is not promised. UNKNOWN, not observed. If the session `cd`s, the two can differ.
  - Budget: "SessionEnd hooks share a 1.5-second budget", raised to a configured `timeout` up to 60 s.
  - Resume and `/clear`: SessionEnd fires with `reason` `resume` or `clear`. Superseded premise: the mods API declaration says `/clear` continues under a new id, so SPEC B-F5 and O6 record a pending rebind on `clear` and `resume` and apply it at the next SessionStart instead of keying on an unchanged `session_id`.
- **Subagent PreToolUse: DOCUMENTED.** The payload carries `agent_id` and `agent_type`. The docs say `session_id` is "Current session identifier". They do not state it is the parent's id, and there is no `parent_session_id` field. So parent `session_id` in subagents is UNKNOWN by docs. B3 should be checked by a live capture before the engine relies on it.

## Q5. Mods under `claude -p`: DOCUMENTED (local `plugin-authoring` skill reference, 2.1.286; not re-observed on 2.1.289)
- "A headless `claude -p` always loads fresh". For a `--plugin-dir` plugin whose module was not loaded, "the switch being off included, which `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` in that process's environment turns on".
- So a gating switch exists, and its name is `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`.
- Hot reload is not offered under `-p`. A long-lived headless session needs `CLAUDE_CODE_PLUGIN_DIR_WATCH=1`.
- The hooks module is not loaded by default under `-p` without the switch. Whether it is on or off by default under 2.1.289 `-p`: UNKNOWN. I did not run a probe, because writing a mod would trip the watch and the probe was not needed.
- B1 tests under `-p` must set `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, and must separately test the no-mods path.
- `claude plugin test <folder>` runs `*.test.ts` against the engine without a session.

## Q6. Reinstall commands: OBSERVED from `--help`, plus a documented restart rule
- **Claude Code:**
  - `claude plugin marketplace update orchestra-distribution`
  - `claude plugin update orchestra@orchestra-distribution`
  - The new version loads "in your next session, or after you run `/reload-plugins`". The help text says "restart required to apply".
  - Installed state: version 1.0.1 at `~/.claude/plugins/cache/orchestra-distribution/orchestra/1.0.1`, scope user.
  - A `version` field in `plugin.json` pins the plugin until it changes, so the bump is required for an update to be seen.
- **Codex** (`codex plugin --help`; the marketplace `orchestra-distribution` is configured in `~/.codex/config.toml` from the GitHub repo, `ref = "main"`):
  - `codex plugin marketplace upgrade orchestra-distribution`
  - `codex plugin remove orchestra@orchestra-distribution`, then `codex plugin add orchestra@orchestra-distribution`.
  - The README names profile install as `python3.11 <plugin>/scripts/orchestra.py install-profiles`. Run it from the installed Codex copy, `~/.codex/plugins/cache/orchestra-distribution/orchestra/<version>/scripts/orchestra.py`. I did not execute it, because it writes `~/.codex/agents`.
- Codex installs from the remote `main`, so the merge to main must happen before the Codex reinstall.
- UNKNOWN: whether `plugin add` over an existing install upgrades in place without `remove`.

## Coverage and gaps
- Commands run: `claude --version`, `claude plugin --help` and its subcommand helps, `codex --version`, `codex plugin --help` and its subcommand helps, plus read-only reads of installed files.
- Not run: any `claude -p` probe, and `install-profiles`.
- Gaps:
  - Runtime `skills:` resolution (Q1).
  - SessionEnd `cwd` equality (Q4).
  - Subagent `session_id` identity (Q4).
  - Default `-p` mod behaviour (Q5).
- Routing: Q1 and Q4 UNKNOWNs go to implementation as live checks in B4 and B3, with the existing fallbacks. No SPEC "settled decision" is found infeasible.

## I2. Upstream skill sources (accepted 2026-10-04)

Fetched with `git clone --depth 1` of each default branch on 2026-10-04. The coordinator re-checked each SHA with `git rev-parse HEAD` and each LICENSE first line.

| Repo | Pinned SHA | License at SHA |
| --- | --- | --- |
| obra/superpowers | 8ca22dba9a94f28898bbce59f2537ff4d87c747d | MIT (Jesse Vincent) |
| mattpocock/skills | d81f3a183412e71a5b1e84ca21bc1a35eea03a60 | MIT (Matt Pocock) |
| garrytan/gstack | 4015c2870b064644131ed6f7cfcc1469cfe9808c | MIT (Garry Tan); NOTICE.md lists Apache-2.0 design material, not in the skills used here |
| github/spec-kit | ae5ade7234be5cb1d975f736c4e06dd46d1326d6 | MIT (GitHub, Inc.) |
| bmad-code-org/BMAD-METHOD | 3cae711ea5274cf7c7cf6e173bb8d7f29cd71497 | MIT (BMad Code, LLC) plus a trademark notice; do not use the mark |

- Claude Code built-ins `security-review` and `simplify`: no published license (`gh api repos/anthropics/claude-code/license` returned 404). Idea level only, own words.
- Pocock layout: `handoff` and `writing-for-agents` live in `skills/productivity/`; `grill-me` and `grill-with-docs` wrap a `grilling` skill.
- gstack has no diff-scope rules file. The scope gate is `bin/gstack-diff-scope` plus a scope line in each of 8 review specialist files.
- Avoid-list text found: superpowers `using-superpowers` "1% chance" bootstrap; the never-pause rule in `executing-plans` and `subagent-driven-development`; gstack `ROOT-SKILL.md` preamble and telemetry.
- Extra candidates for MX: Pocock `research`, `wayfinder`, `wizard`, `to-questionnaire`, `git-guardrails-claude-code`, `pr`; gstack `investigate`, `spec`, `careful`/`guard`/`freeze`, `test-audit`, `context-save`/`context-restore`, `retro`; superpowers `diagnosing-superpowers`.

## Q1 follow-up. Skills preload and mode files: OBSERVED (coordinator probe, Claude Code 2.1.289, 2026-10-04)

- Agent frontmatter `skills:` with two bare names preloads both into a plugin subagent with no tool call. An unknown name is skipped with no error.
- A worker told to read `references/<Mode>.md` from its brief's `Mode:` line did so in 3 of 3 runs. A non-preloaded skill matching the task was invoked in 0 of 3 runs.
- A Workflow `agent()` with `agentType` set to the plugin agent got both preloaded skills and read the mode file (1 of 1 run).
