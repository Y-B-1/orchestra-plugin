# Live matrix

`scripts/live-matrix.py` runs the installed plugin in real headless `claude -p` sessions and checks what the hooks and the engine did. Unit tests cannot show that Claude Code discovers the hooks, fires them in subagents and Workflow agents, or honors their denies; this can. Run it by hand before a release. `scripts/check.sh` never runs it: it costs tokens and needs a signed-in `claude` CLI.

## What it tests

Sixteen scenarios, each in its own scratch repository with a bare origin, so nothing touches a real project. `--list` prints each id with one line on what it proves.

- Guard modes: `g0` (no run), `g1` minimal, `g2` normal, `g3` protect.
- Autonomy: `a1` git limits while armed, `a2b` ledger, settings and cron locks, `a3b` the owner-only `approved` receipt.
- Capture: `d1` Agent tool, `d2` Workflow, `w1` worktree wave, `h2b` board line after a captured report.
- Worker limits: `d3` missing Mode line, `d4` lease and delegation denies.
- Run flow: `h1` the Stop block, `r1b` resume and `start --recover`.
- Install: `i1` install and uninstall in a clean profile.

Every check reads the stream-json events (tool calls, results, hook responses) or the engine state. None trusts what the model says about itself.

## How to run

```
python3 scripts/live-matrix.py OUT_DIR                 # all scenarios
python3 scripts/live-matrix.py OUT_DIR g1 d1           # chosen scenarios
python3 scripts/live-matrix.py --list
```

- `--plugin DIR`: the installed plugin to test. Default: the newest version under `~/.claude/plugins/cache/orchestra-distribution/orchestra`.
- `--model ID`: model for every session. Default `claude-sonnet-5-5`.
- `--parallel N`: scenarios at once. Default 4.
- `--source DIR`: marketplace source for `i1`. Default: this repository's root.
- `OUT_DIR`: output root. Each scenario writes `OUT_DIR/<id>/` with `repo/`, `origin.git/`, one `run<N>.jsonl` and `run<N>.err` per session, and `result.json`.

Python 3.11 or newer and Git are needed, and nothing else.

## Cost and time

About 20 sessions in all. At `--parallel 4` the full matrix takes about 15 minutes. Run a few ids while debugging one.

## Reading results

The last lines are a table of scenario, checks, failed, seconds and the names of failed checks, then `RESULT: PASS` or `RESULT: FAIL`. The exit code is 1 when any check failed, any scenario crashed or any scenario ran no checks.

For a failure open `OUT_DIR/<id>/result.json`: each check has its detail, and each session lists its tool calls and hook responses. `run<N>.jsonl` holds the raw events. A check that says `model never ran it` means the model skipped a command; rerun that id before calling it a plugin bug. Model behavior varies, so a single flaky miss is not a regression, but a repeated one is.

## Accepted limits

- Sessions are headless (`-p`); the interactive prompt UI and permission dialogs are not exercised.
- Sessions run with `bypassPermissions`, so a deny seen here comes from Orchestra's hooks, not from a permission prompt. Behavior under other permission modes is not covered.
- The Python version is not varied: `run-hook.sh` picks the newest interpreter on the machine, so the matrix uses whichever it finds. Python 3.11 and 3.13 are covered by `scripts/check.sh`.
- The scenarios prompt a model to run fixed commands; a model that refuses or rewrites a command makes that check fail as not run, not as a guard result.
