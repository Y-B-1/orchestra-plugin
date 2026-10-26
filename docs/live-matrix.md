# Live matrix

`scripts/live-matrix.py` runs the installed plugin in real headless `claude -p` sessions and checks what the hooks and the engine did. Unit tests cannot show that Claude Code discovers the hooks, fires them in subagents and Workflow agents, or honors their denies; this can. Run it by hand before a release. `scripts/check.sh` never runs it: it costs tokens and needs a signed-in `claude` CLI.

## What it tests

Twenty-two scenarios, each in its own scratch repository with a bare origin, so no real project is touched. The engine's run state is the exception: it lives in the real state home (see Run state below). `--list` prints each id with one line on what it proves.

- Guard modes: `g0` (no run), `g1` minimal, `g2` normal, `g3` protect.
- Autonomy: `a1` git limits while armed, `a2b` ledger, settings and cron locks, `a3b` the owner-only `approved` receipt, `a4` scratchpad deletes on a decoy `/tmp/claude-99999` tree (a temp root, a project's sessions and another session's directory are denied; a plain temp file glob is allowed).
- Capture: `d1` Agent tool, `d2` Workflow, `w1` worktree wave, `h2b` board line after a captured report.
- Worker limits: `d3` missing Mode line, `d4` lease and delegation denies.
- Run flow: `h1` the Stop block, `r1b` resume and `start --recover`.
- Install: `i1` install and uninstall in a clean profile.
- Model fit: `m1` SessionStart records the session model, the engine refuses an inline card on another model and still allows its worker start.
- Role skills: `s1` the main session loads `orchestra:orchestra-design` and `orchestra:orchestra-build` with the Skill tool.
- Track: `t1` the main session runs the first track card inline, sends the disjoint side card to a worker before accepting, and the track then names the next card (Opus session). `t2` a Haiku session is refused an inline Sonnet card with "Model fit" and the track shows coordinator work. `t3` native tasks (`CLAUDE_CODE_ENABLE_TODO_TOOLS=1`): `TaskCreate` carries `step 1` for the first card and a later task call shows the step change; it records a `skipped (reason)` row, not a failure, when the task tools are missing or no task call reaches the transcript (the board mod does not run in every headless build).

Every check reads the stream-json events (tool calls, results, hook responses) or the engine state. None trusts what the model says about itself.

## How to run

```
python3 scripts/live-matrix.py OUT_DIR                 # all scenarios
python3 scripts/live-matrix.py OUT_DIR g1 d1           # chosen scenarios
python3 scripts/live-matrix.py --list
```

- `--plugin DIR`: the installed plugin to test. Default: the newest version under `~/.claude/plugins/cache/orchestra-distribution/orchestra`.
- `--plugin-dir DIR`: load this plugin directory into every session in place of the installed copy, for example `plugins/orchestra` of a release candidate. Claude Code then loads only that copy (one SessionStart answer), so a candidate is tested live before it ships.
- `--model ID`: model for every session. Default `claude-sonnet-5-5`.
- `--parallel N`: scenarios at once. Default 4.
- `--repeat N`: runs of each scenario. Default 1, which keeps `OUT_DIR/<id>/`. With N above 1 each run gets its own `OUT_DIR/<id>.rK/`, a scenario passes only when every run passes, and the summary names each scenario whose runs disagreed as a `FLIP` with the failing checks. One run hides flaky behavior: a break can show in only some runs, so run each scenario more than once.
- `--source DIR`: marketplace source for `i1`. Default: this repository's root.
- `OUT_DIR`: output root. Each scenario writes `OUT_DIR/<id>/` with `repo/`, `origin.git/`, one `run<N>.jsonl` and `run<N>.err` per session, and `result.json`.

Python 3.11 or newer and Git are needed, and nothing else.

## Run state

Each scenario that starts a run leaves its run state under `~/.local/state/orchestra/<identity>` (`$XDG_STATE_HOME/orchestra/<identity>` when `XDG_STATE_HOME` is an absolute path), not under `OUT_DIR`. The harness never removes it. `<identity>` is the first 24 hex digits of the SHA-256 of the scenario's repository path, `OUT_DIR/<id>/repo`, so a scenario's directory is found from that path. To remove one scenario's run state:

```
ID=$(python3 -c 'import hashlib, os, sys; print(hashlib.sha256(os.path.realpath(sys.argv[1]).encode()).hexdigest()[:24])' OUT_DIR/g1/repo)
rm -rf ~/.local/state/orchestra/"$ID"
```

Remove it before a rerun of the same scenario: `OUT_DIR/<id>/` is recreated at the same path, so the same identity comes back and the rerun can find the old run.

## Cost and time

About 25 sessions in all. At `--parallel 4` the full matrix takes about 15 minutes. Run a few ids while debugging one.

## Reading results

The last lines are a table of scenario, checks, failed, seconds and the names of failed checks, then `RESULT: PASS` or `RESULT: FAIL`. The exit code is 1 when any check failed, any scenario crashed or any scenario ran no checks.

For a failure open `OUT_DIR/<id>/result.json`: each check has its detail, and each session lists its tool calls and hook responses. `run<N>.jsonl` holds the raw events. A check that says `model never ran it` means the model skipped a command; rerun that id before calling it a plugin bug. Model behavior varies, so a single flaky miss is not a regression, but a repeated one is.

## Accepted limits

- Sessions are headless (`-p`); the interactive prompt UI and permission dialogs are not exercised.
- Sessions run with `bypassPermissions`, so a deny seen here comes from Orchestra's hooks, not from a permission prompt. Behavior under other permission modes is not covered.
- The Python version is not varied: `run-hook.sh` picks the newest interpreter on the machine, so the matrix uses whichever it finds. Python 3.11 and 3.13 are covered by `scripts/check.sh`.
- The scenarios prompt a model to run fixed commands; a model that refuses or rewrites a command makes that check fail as not run, not as a guard result.

The harness writes a `.live-matrix` marker in each scenario directory it makes, and replaces an existing `OUT_DIR/<id>` only when that marker is present; any other directory stops the run with an error naming it.

The d4 check "worker lease-free status allowed" counts only a worker command that runs `orchestra.py status` without `--lease`; `git status` does not count.
