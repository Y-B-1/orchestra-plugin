# Benchmark: Orchestra against plain Claude Code and other skill packs

## Orchestra 3.3.0 (2026-10-29)

**Result:** on two new tasks built from the owner's real rework patterns, Orchestra 3.3.0 matched 3.2.0 on time, cost and hidden tests and scored highest on the blind rubric. It beat plain Claude Code, mattpocock/skills and pstack 0.9.108 (47c6f80) on hidden tests and rubric, and was 18% faster than plain and 30% faster than pstack.

### Tasks F and G

Both come from about 1,580 owner prompts in real projects, mined for the places the owner had to correct or re-ask. Each is about 1,800 words in the owner's dictation style, with corrections in the middle ("wait, no").
- **F, the numbers must be right (35 hidden tests):** a fix asked for "all" places, bounded scores whose label, bar and value agree, duplicate clients in aggregates, a 30-day window, a ranking that makes sense, a dark-theme-only bug, and an approved data migration.
- **G, finish the whole flow (40 hidden tests):** a six-rule sign-in change, a page that must match a reference page, three navbar variants, an approved migration, cleanup of dead features, an adjacent bug to report rather than touch, and an honest status at the end.

Both reference solutions pass every hidden test and all four project checks; the untouched app passes only the regression tests.

### Results (mean of F and G, 2 runs per task per arm)

| Arm | Time | Cost | Hidden tests | Rubric | Repair work |
|---|---|---|---|---|---|
| Orchestra 3.2.0 | 11.9 min | $3.39 | 99.4% | 94.5% | 4.2 |
| **Orchestra 3.3.0** | 12.1 min | $3.38 | 99.3% | **96.0%** | 4.5 |
| mattpocock/skills@59db609 | 13.0 min | $2.87 | 97.3% | 93.7% | 5.5 |
| Plain Claude Code | 14.7 min | $3.47 | 96.0% | 92.3% | 5.8 |
| pstack 0.9.108 (47c6f80) | 17.2 min | $4.58 | 96.7% | 91.3% | 6.5 |

Every run pushed its branch and passed all four project checks. The keep rule (quality gain in percent minus half the time increase in percent above zero) holds against 3.2.0: rubric +1.6%, hidden tests equal, time +1.7%.

### Limits of this round

- **Few runs:** 2 per task per arm. One 3.3.0 run on F took 19.6 minutes against 8.3 for the other with the same plan shape (same units, same review), so differences under about 20% are within noise.
- **Rubric scoring:** a judge sometimes split one rubric row into several; the report now folds scores onto the rubric rows, so totals compare.

---

## Orchestra 3.2.0 (2026-10-29)

**Result:** on five long multi-request prompts (tasks A to E), Orchestra 3.2.0 delivered a pushed branch in **9.5 minutes per task on average, against 11.8 for 3.0.0 and 12.4 for plain Claude Code**. It passed **98.8%** of the hidden tests (3.0.0: 98.4%, plain: 98.7%), and the blind judge found the least remaining repair work of the three (**4.3 points**, against 5.1 and 4.7). It cost **$3.53 per task**, 12% more than 3.0.0 ($3.16) and plain ($3.18). Every 3.2.0 run pushed its branch and passed all four project checks.

3.2.0 brings back the eleven agents and the role and situation skills of 2.15 (see `CHANGELOG.md`). The owner's keep rule for any change: keep it when the quality gain in percent minus half the time increase in percent is above zero. 3.2.0 is faster and slightly better than 3.0.0, so it passes.

### Tasks D and E

Tasks A to C are described below under 3.0.0. Tasks D and E are longer: 18 asks each, 30 and 31 hidden tests, and reference diffs of about 1,650 lines. Each holds traps for the situations the 2.15 lessons cover: a misleading bug report, two conflicting asks, a data migration, unsafe HTML in user text, a race between requests, a new status that must show everywhere, a midnight boundary, keyboard access in a new dialog, and an owner suggestion that would break something. Both reference solutions pass every hidden test and all four checks.

### Results (mean per task)

| Task | Plain: time / hidden | 3.0.0: time / hidden | 3.2.0: time / hidden |
|---|---|---|---|
| A | 13.1 min / 52 of 52 (n=2) | 9.8 min / 76 of 78 (n=3) | 8.4 min / 26 of 26 (n=1) |
| B | 14.4 min / 56 of 56 (n=2) | 11.4 min / 84 of 84 (n=3) | 9.5 min / 28 of 28 (n=1) |
| C | 10.4 min / 60 of 60 (n=2) | 9.2 min / 90 of 90 (n=3) | 9.9 min / 60 of 60 (n=2) |
| D | 9.4 min / 29 of 30 (n=1) | 15.4 min / 58 of 60 (n=2) | 7.3 min / 29 of 30 (n=1) |
| E | 14.7 min / 30 of 31 (n=1) | 13.0 min / 91 of 93 (n=3) | 12.5 min / 121 of 124 (n=4) |
| **Mean** | **12.4 min, $3.18, repair 4.7** | **11.8 min, $3.16, repair 5.1** | **9.5 min, $3.53, repair 4.3** |

The 3.0.0 column now includes newer runs on a busier machine, so its time is higher than the 7.4 minutes reported for three tasks below. All three columns in this table ran in the same period.

### What the versions in between taught

- **3.1.0 (not released)** put every lesson into every builder and reviewer. It was 36% slower than 3.0.0 with no quality gain. Two split runs showed both halves cost time: builder rules alone and review rules alone were each about 35% slower on tasks C and E, and reviewers ran the diff scan 2 or 3 times each.
- **3.2.0 first build** loaded lessons only by situation and matched 3.0.0's time, but all three runs on task E failed the booking-dialog validation trap. The builder that loaded `frontend-proof` disabled the submit button until data loaded, so a click showed no error. A first rule ("never disable a submit for empty or loading fields") passed the trap in 2 of 3 runs; the third returned early from the submit handler instead. The final rule, "a submit never fails silently", covers both forms, and the trap passed in all 4 task-E runs with it.
- **Final review** found 9 defects in the diff scan and in rules that contradicted each other across skills (three different review-round caps). All were fixed with a test each and passed a scoped re-review.

### Limits of this round

- **Few runs:** 1 to 4 runs per task for 3.2.0. Run-to-run spread on one task is up to 2.5 times (3.0.0 on task B: 6.6 to 20.6 minutes), so differences under about 20% are within noise.
- **Cost:** 3.2.0 costs about 12% more per task. Most of it comes from task E, whose 1,900-line diffs draw long Opus reviews.
- **One session ended early:** one 3.2.0 run on task D ended while its builders were still running (the headless session exited after its turn), and it is excluded. The plugin cannot prevent this in `-p` mode; `/orchestra:goal` keeps an interactive session going.

---

# Orchestra 3.0.0 (2026-10-28)

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
