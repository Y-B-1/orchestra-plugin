# Orchestra 3.2 plan: no regression, best of 2.15 and 3.x

Owner decisions (2026-10-29), in the owner's terms:

1. **No regression.** A new version keeps every capability, performance level and function of the old one and only makes it better. A role, skill or step is removed or folded only when a measured comparison shows no loss.
2. **Skills: both layers.**
   - Per-agent skills, as in 2.15, rewritten as the best version of themselves, updated with the newest Pocock and pstack ideas where each agent needs them.
   - One shared skills directory any agent can load, the main session included. The main `orchestra` skill teaches when to use it.
3. **Roles: restore all, then measure.** Restore every 2.15 role with its model and effort. Fold two roles, or add one (for example an Opus role), only after the benchmark shows which choice is better. Check whether an operator adds value over the main session doing the same work.
4. **Review loop, pre-PR only.** It never runs after a single builder; builders check their own units. Once all work has landed, before the PR opens:
   - An Opus subagent reviews the whole diff once. The main session never reviews.
   - A Sonnet builder repairs the findings.
   - An Opus re-review checks only the files the repair touched, and the loop repeats until clean.
   - After 3 rounds, a finding that still survives goes to an Opus repair.
8. **Use every resource at once.** The main session works an inline unit while a Workflow runs the other units in parallel, and single subagents start only when needed (a worktree-isolated unit, research). The main session coordinates and builds at the same time; it never sits idle. Its inline unit is real work, sized to finish before the Workflow returns. The routing table only chooses model and role per unit and does not change this shape.
9. **Keep rule, approved.** Keep a change when quality gain % − 0.5 × time increase % > 0.
5. **Permissions.** Requirements in, an open PR out, with no stops. Only merging into the default branch is blocked. Removing stale worktrees and branches is always allowed. Claude Code's own permission system handles anything else destructive.
6. **Dropped for good.** Autonomy mode (`/orchestra:goal` does the same job), the old board and the cards. A new view of "what I asked, what is done, what is left" will be designed with Claude Code mods.
7. **Keep rule, a matrix.** Weigh each change on four things together:
   - quality gain in percent (hidden tests, traps caught, judge repair work);
   - turns;
   - how often it got things wrong;
   - time and cost.

   A large quality gain at a small time cost stays. A marginal quality gain at a large time cost goes.

## Open questions
- The design of the progress view.

## Benchmark result: 3.1.0 against 3.0.0 (one run each, 2026-10-30)

| Task | 3.0 time | 3.1 time | 3.0 hidden | 3.1 hidden | 3.0 repair | 3.1 repair |
|---|---|---|---|---|---|---|
| A | 7.7 | 7.8 | 25/26 | 26/26 | 5 | 6 |
| B | 7.1 | 8.4 | 28/28 | 28/28 | 5 | 3 |
| C | 8.4 | 14.0 | 30/30 | 30/30 | 4 | 9 |
| D | 9.4 | 10.1 | 29/30 | 29/30 | 5 | 10 |
| E | 9.5 | 17.0 | 31/31 | 30/31 | 5 | 7 |

Tasks A to C use the lean5 runs for 3.0 (the same skill). 3.1 averages 11.5 minutes against 8.4 (+36%), with no quality gain and more repair work (7.0 against 4.8). By the keep rule, 3.1 does not ship as built.

Where the time went:
- Review: on task C, 3.1 reviewers took 4.5 to 5 minutes each against about 1 in 3.0, and found less of what the judge found. They loaded `review.md` and ran `lean.py check`.
- Scheduling: on task E, the main session put the booking unit after two other units, a third serial wave that 3.0 did not have.
- Builders loaded `frontend.md` and `tests.md` in most units; builder times look similar on task D.

Next: two ablation arms (builder-side changes only; review-side changes only) on tasks C, D and E, plus a second 3.0 and 3.1 run on task E to measure run-to-run noise.

## Final result (2026-10-30)

The final 3.2.0 code (9 runs over tasks A to E) against 3.0.0 (14 runs): 9.5 against 11.8 minutes per task (19% less time), 98.8% against 98.4% hidden tests, judge repair 4.3 against 5.1, cost $3.53 against $3.16 (+12%). Keep rule: quality gain is positive and time fell, so 3.2.0 is kept. Details in `docs/BENCHMARK.md`.
