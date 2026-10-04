Sentinel: orchestra/references/briefs.md
Stub: B4 skeleton; ticket S1 rewrites this file and removes this line.

# Assignment guide

Write one bounded brief per worker. Include:

1. Objective, `Mode:` line (a final-review brief also a `Lens:` line), immutable starting artifact and requested output path.
2. Owned files/resources, sibling ownership, worktree, prerequisites and acceptance checks.
3. Applicable project instructions, path rules, design vocabulary and policy revision. Read linked source rules first and carry their operative requirements inline; a link alone does not carry a rule into an empty worker context.
4. Tools available, authorization limits and report contract.

Workers preload the orchestra-worker skill, so a brief does not restate the worker contract. A card whose brief file lacks its `Mode: <mode>` line is rejected by the engine.
