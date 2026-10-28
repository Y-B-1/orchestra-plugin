# Benchmark: Orchestra 3.0.0 against plain Claude Code and other skill packs

**Result:** on three long multi-request engineering prompts, Orchestra 3.0.0 delivered a pushed branch in **7.4 minutes per task on average, against 12.7 for plain Claude Code** (42% less time), at the same cost (**$2.76 against $2.77**). It passed **167 of 168** hidden tests, and the blind judge's remaining repair work was close to plain Claude Code's (4.7 against 4.2 points). Orchestra 2.15.3 took **21.4 minutes and $8.03** per task, about three times the time and the cost of 3.0.0.

The kit that produced these numbers is in [`bench/`](../bench/README.md): the fixture app, the three tasks with their hidden tests and reference solutions, the runner, the blind judge prompt and pinned versions of the comparison arms.

## Setup

- **Fixture:** Pulse, a Vite + React + TypeScript trading dashboard of about 6,200 lines over seven pages, with vitest and ESLint. It has six planted bugs that show only as symptoms, and test debt for the cleanup asks.
- **Tasks:** three prompts of 12 or 13 asks each, written the way a developer dictates a long list: small tweaks, bug reports, a refactor, two or three new features with dependencies between them, test cleanup and docs. They are modeled on real multi-request prompts from the author's own sessions. Each has 26 to 30 hidden tests, 7 of them regression tests.
- **Fairness checks:** an independent audit fixed 19 wording and test problems before the runs. Each task's reference solution passes every hidden test, and the untouched app passes only the 7 regression tests.
- **Runs:** one headless session per run, model Opus 5.5, a clean environment (no user settings, no other plugins), two runs at a time. The only difference between arms is the plugin directory.
- **Arms:** plain Claude Code (no plugin); Matt Pocock's skills (`mattpocock/skills` at `59db609`); pstack (`michael-denyer/pstack-claude` at `36885ea`); Orchestra 2.15.3; Orchestra 3.0.0.
- **Measures:** time from the prompt to the last push; cost from the session result; hidden tests run on the pushed branch; the four project checks (typecheck, lint, test, build); and a blind judge (a second Opus session that does not know the arm). The judge scores each ask and lists every fix still needed with a size; repair points add up those fixes, the failed hidden tests and the failed checks. Lower repair is better.

## Results by task

Each cell is the mean over the runs shown in `n`. Time is minutes from the prompt to the pushed branch. Hidden tests are summed over runs. Repair is the judge's fix-work points still needed (lower is better). Peak is the most agents running at once in any run.

### Task A

| Arm | n | Time (min) | Cost (USD) | Hidden tests | Repair | Peak agents | All 4 checks pass |
|---|---|---|---|---|---|---|---|
| Plain Claude Code | 2 | 13.1 | 2.36 | 52/52 | 5.5 | 0 | yes |
| Matt Pocock skills | 2 | 9.9 | 2.58 | 52/52 | 3.0 | 0 | yes |
| pstack | 2 | 14.2 | 4.17 | 52/52 | 3.5 | 1 | yes |
| Orchestra 2.15.3 | 2 | 21.4 | 8.00 | 52/52 | 5.0 | 3 | yes |
| Orchestra 3.0.0 | 2 | 7.8 | 2.87 | 51/52 | 6.0 | 5 | yes |

### Task B

| Arm | n | Time (min) | Cost (USD) | Hidden tests | Repair | Peak agents | All 4 checks pass |
|---|---|---|---|---|---|---|---|
| Plain Claude Code | 2 | 14.4 | 3.14 | 56/56 | 4.0 | 0 | yes |
| Matt Pocock skills | 2 | 12.1 | 3.59 | 56/56 | 3.0 | 0 | yes |
| pstack | 2 | 13.4 | 4.51 | 56/56 | 3.5 | 1 | yes |
| Orchestra 2.15.3 | 2 | 20.6 | 8.08 | 56/56 | 5.0 | 3 | yes |
| Orchestra 3.0.0 | 2 | 6.8 | 2.58 | 56/56 | 4.0 | 5 | yes |

### Task C

| Arm | n | Time (min) | Cost (USD) | Hidden tests | Repair | Peak agents | All 4 checks pass |
|---|---|---|---|---|---|---|---|
| Plain Claude Code | 2 | 10.4 | 2.80 | 60/60 | 3.0 | 0 | yes |
| Matt Pocock skills | 1 | 18.8 | 3.37 | 30/30 | 4.0 | 0 | yes |
| pstack | 1 | 17.1 | 3.64 | 30/30 | 7.0 | 1 | yes |
| Orchestra 2.15.3 | 1 | 23.2 | 7.98 | 27/30 | 8.0 | 2 | yes |
| Orchestra 3.0.0 | 2 | 7.7 | 2.83 | 60/60 | 4.0 | 2 | yes |

## Totals over the three tasks

| Arm | Runs | Mean time per task (min) | Mean cost per task (USD) | Hidden tests | Mean repair |
|---|---|---|---|---|---|
| Plain Claude Code | 6 | 12.7 | 2.77 | 168/168 | 4.2 |
| Matt Pocock skills | 5 | 12.6 | 3.14 | 138/138 | 3.2 |
| pstack | 5 | 14.5 | 4.20 | 138/138 | 4.2 |
| Orchestra 2.15.3 | 5 | 21.4 | 8.03 | 135/138 | 5.6 |
| Orchestra 3.0.0 | 6 | 7.4 | 2.76 | 167/168 | 4.7 |

## Design iterations

Each 3.0 candidate on the same three tasks (mean over its runs).

| Candidate | Runs | Mean time (min) | Mean cost (USD) | Hidden tests | Mean repair | Peak agents |
|---|---|---|---|---|---|---|
| lean | 2 | 36.7 | 3.01 | 54/54 | 5.0 | 5 |
| lean2 | 3 | 9.0 | 2.29 | 81/84 | 6.7 | 6 |
| lean3 | 3 | 10.3 | 2.83 | 84/84 | 4.3 | 5 |
| lean4 | 3 | 12.0 | 2.80 | 83/84 | 6.3 | 6 |
| lean5 | 6 | 7.4 | 2.76 | 167/168 | 4.7 | 5 |

All runs passed all four project checks.

## What made the difference

- **Parallel builders.** Orchestra 3.0.0 ran 2 to 5 builder agents at once in one Workflow; the other arms did the work in one session (pstack ran one agent at a time). On these tasks that cut the time by 26% to 53% against plain Claude Code.
- **No process tax.** 2.15.3 spent its extra time on the run itself, not the code: reading long references, engine refusals on brief format, reshaping review receipts, and in one run a scheduled check-in that held a finished session open for 26 minutes. 3.0.0 has no engine, no board and no receipts.
- **Start the builders first.** The best candidate starts the Workflow before the main session makes any edit of its own, and runs the review as two or three parallel reviewers by area while the checks and test cleanup run.
- **Shared rules travel with every brief.** Two candidates missed "put an arrow on every price change" on a page that another builder wrote in parallel. Every builder brief now carries each such rule with the shared helper that implements it, and the reviewer searches the whole diff for each one. After that change, all three of the final candidate's second runs passed every hidden test.
- **Quality.** Parallel builders left slightly more small design fixes than a single session (4.7 against 4.2 repair points). Pocock's skills left the fewest (3.2) at about plain Claude Code's speed.

## Design iterations

Each candidate fixed what the one before it showed. `lean` lost an hour to a test command that hung; `lean2` added bounded commands (`lean.py run SECONDS -- CMD`) and fanned out properly but let builders change code they did not own; `lean3` added the seam-focused review and pattern-following builders; `lean4` made the final message stand on its own; `lean5` (shipped as 3.0.0) starts builders first, splits the review and carries shared rules into every brief.

## Limits

- **Small sample.** Each cell has one or two runs, so differences of a minute or one repair point are within run-to-run noise. 3.0.0 had the lowest mean time on all three tasks; against plain Claude Code it cut the time by 40% on task A, 53% on task B and 26% on task C. One Pocock run on task A tied it (7.7 minutes).
- **One fixture.** All tasks use one mid-size React app. Larger repositories with slow test suites will change the absolute numbers.
- **Two runs at a time.** Runs shared one machine in pairs, which can slow both runs of a pair a little.
- **One test fix after the runs.** Two hidden tests picked an option the moment a dropdown appeared, which failed when a page filled the dropdown just after loading (a user sees it fill in). The tests now wait up to 4 seconds for the option. Every task A and C run was rescored; two runs changed (one `lean2` run and one `lean5` run), and both were rejudged.
- **Judge.** The judge is a model, not a person. It sees the spec, the rubric, the hidden test results, the final message and the diff, never the arm's name.
