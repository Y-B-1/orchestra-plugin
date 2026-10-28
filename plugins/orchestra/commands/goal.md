---
description: Work on a goal without stopping until every ask is done and the branch is pushed
argument-hint: what you want done
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lean.py" goal set`

Goal from the owner:

$ARGUMENTS

1. The goal is set (the line above). Load the orchestra skill and follow it: write the ask ledger at the path above, start every independent ask at once, review once at the end.
2. Do not stop to ask questions; make sensible calls and list them at the end. A Stop hook keeps you going until every ledger line is done or dropped with a reason and the branch is pushed.
