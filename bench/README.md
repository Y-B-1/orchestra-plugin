# Orchestra benchmark kit

A reproducible benchmark that compares Orchestra with plain Claude Code and other skill packs. Each run is one headless Claude Code session (model `claude-opus-5-5`, clean environment, no settings sources, bypass permissions, 110 minute limit) that gets a task prompt in a fresh clone of the Pulse fixture app and must push a branch to a local bare origin.

## What it measures

- Time to last push, and total wall time.
- Cost in USD from the session result.
- Parallelism: summed agent busy time (Agent tool and Workflow subagents, read from the session transcripts) over time to last push. Peak concurrent agents.
- Hidden tests: the task's `hidden/` tests copied into the pushed branch and run with vitest.
- Project checks: `typecheck`, `lint`, `test` and `build` run on the pushed branch.
- A blind judge, a second Opus session that sees only the spec, rubric, hidden test results, final message and diff. It scores each ask 0 to 2 and lists defects with a fix size. Repair points combine failed hidden tests, defect sizes (S 1, M 3, L 8) and 3 per failed check.

## Layout

- `bench.py`: the runner (`run`, `score`, `judge`, `queue`, `queue-file`, `report`).
- `fixture/`: the Pulse app. `npm ci` runs in it once on first use.
- `tasks/A`, `B`, `C`: `prompt.md` (given to the agent), `spec.md` and `rubric.md` (given to the judge), `hidden/` tests, `reference.patch`.
- `fetch-arms.sh`: fetches the comparison arms into `arms/` at pinned versions.
- `runs/`, `arms/`, `origin.git/`: generated, gitignored.

Arms: `plain` (no plugin), `orchestra` (this checkout's `plugins/orchestra`), `orchestra-2.15.3` (the tag's plugin), `pocock` (mattpocock/skills) and `pstack` (michael-denyer/pstack-claude).

## Run it

```
bench/fetch-arms.sh
printf 'plain:A:0\norchestra:A:0\n' > /tmp/queue.txt
python3 bench/bench.py queue-file /tmp/queue.txt
python3 bench/bench.py report
```

Queue lines are `arm:task:rep`. The queue file is re-read before each pair, so it can be edited while it runs; two runs go at a time. A run that fails twice is marked skipped. Needs `claude`, `git`, `node` and `npm` on PATH, Python 3.11+, and about 4 GB free disk (node_modules is cloned copy-on-write on macOS).

## Cost

Each run is a full Opus session plus a judge session, about $2 to $8 per run. `scripts/check.sh` never runs the benchmark.
