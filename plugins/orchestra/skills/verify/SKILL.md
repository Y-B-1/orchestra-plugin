---
name: verify
description: "Load when a flow has many states and events (booking, payments, sync, multi-step forms), or the repo has no way to run and drive the real app. Not for a single-screen change that the repo's e2e runner already drives."
---
# Verify

## Pick the part
- The repo has no scripted way to start the real app and exercise a flow: build a driver. Read `references/driver.md`.
- A driver exists and the flow, route, command or UI it drives changed: update the driver in the same change. Read `references/driver.md`, section Maintain.
- The flow has three or more states and several events (booking, payments, sync, wizards): model it as a statechart before you code or test it. Read `references/statechart.md`.
- Any ask that ends in "done", "fixed" or "works": apply the proof rules below.

## Prove it works
- Evidence is a command and its output. A claim, a self-report, "it compiles" and a green earlier run are not evidence.
- Check the real artifact: run the feature, read the actual value, open the diff. Do not infer from file times, cached screenshots or derived state.
- Record the exit code before you read the log. Never pipe to `tail` and call that the result.
- Before you report success (merged, sent, started), read the real state: the process, the row, the ref.
- When a check fails, suspect your observation method before the system. Then confirm the check can fail: a failing run counts only when the failure text is the mismatch you predicted. An exception, an empty list and a real mismatch all print red.
- A probe that a new build must pass keys on behavior only the new build produces, not on a version field the old build also prints.
- Name the record each fact came from. A fact rebuilt from the owner's paste when a file holds it is not proven.
- A state or step you could not reach is "not checked". Never report it as working.
- Prefer a script that re-runs the same comparison over one look. Keep the script in the repo when the work is large or the flow will change again.

## Rules for any part
- Fix a checkout that does not build or start before you write a driver. A driver written on a broken base teaches wrong steps.
- Run the driver once end to end before you hand it over. An unrun driver is a draft.
- Teardown kills only what you started, never by process name. It removes instances and scratch state, never the evidence.
- Do not edit product code to make a driver pass. A flow that no longer behaves as the driver says is either stale driver (fix it) or a regression (report it).
- Add no guard, block or confirmation step for this. Orchestra blocks only a merge into the default branch.

Sources: pstack-claude@47c6f80 create-verification-skill, maintain-verification-skill, statechart, principle-prove-it-works; orchestra v2.15.3 operate gate and frontend rules.
