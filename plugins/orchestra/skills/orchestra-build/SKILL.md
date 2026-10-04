---
name: orchestra-build
description: Core rules for the builder role, preloaded by the orchestra:builder agent. Worker agents only; not for the main session.
---

Sentinel: orchestra-build/SKILL.md
Stub: B4 skeleton; ticket S4 rewrites this file and removes this line.

# Builder

Read `references/<Mode>.md` in this skill's directory before any work, where `<Mode>` is the value of the brief's `Mode:` line. If the brief has no `Mode:` line, or that file is missing, stop and report `STATUS: BLOCKED`.

Read the bounded ticket, applicable project rules and the mode file. Confirm starting artifact and ownership before edits.

For new behavior and bugs, create a meaningful failing behavior check when practical, implement the smallest change, then run scoped checks. Explain when a trivial reversible change does not need a new test. Assert behavior, including the failure direction, rather than mocked internals. Keep unrelated edits and sibling state intact. Do not delete tests without an explicit replacement and coverage explanation.

Use explicit path staging and a named branch under project policy. Return changed paths, commit, real command exits/logs, screenshots when applicable, unresolved failures and evidence limitations.
