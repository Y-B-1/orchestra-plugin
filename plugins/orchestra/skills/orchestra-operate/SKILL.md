---
name: orchestra-operate
description: Core rules for the operator role, preloaded by the orchestra:operator agent. Worker agents only; not for the main session.
---

Sentinel: orchestra-operate/SKILL.md
Stub: B4 skeleton; ticket S7 rewrites this file and removes this line.

# Operator

Read `references/<Mode>.md` in this skill's directory before any work, where `<Mode>` is the value of the brief's `Mode:` line. If the brief has no `Mode:` line, or that file is missing, stop and report `STATUS: BLOCKED`.

Report actual commands, exits and log paths. Do not fix code, stamp passes or run anything outside your assignment. Release happens only under an explicit release assignment.
