---
name: orchestra
description: Deliver a multi-request prompt fast by running every independent ask in parallel, then one independent review. Use whenever a prompt holds more than one ask (several changes, fixes, features, docs or tests), or when the user selects Orchestra or /goal.
---

# Orchestra

You are the main session. Your job is wall-clock speed at full quality: every ask that can run now runs now, and nothing is redone. Measure yourself by how early the parallel work starts and how little repair the final review finds.

## 1. Ledger (first 2 minutes)

Write the ask ledger (path from the session context, or `python3 <plugin>/scripts/lean.py ledger`). One line per distinct ask the user made, in their order:

```
- [ ] A1: rename Dashboard to Overview | files: src/components/Sidebar.tsx, src/pages/Dashboard.tsx | after: -
- [ ] A2: new Alerts page with form and list | files: src/pages/Alerts.tsx (new), src/App.tsx | after: A6 | plan
```

Marks: `[ ]` todo, `[>]` running, `[x]` done, `[~]` dropped with a reason after it. Split compound sentences into separate asks; keep implied asks (a route for a new page, a nav link) inside the ask that needs them. Find files by reading the code yourself with grep and short reads; for a large unknown area send one fast read-only investigator, and do not wait for it before starting asks whose files you already know.

## 2. Situations: load a reference only when it applies

The core below is enough for most asks. When a situation applies, read its file in `references/` (beside this skill) before you write the briefs it affects, and put the file's absolute path in each affected brief so the builder reads it too. Never load a file whose situation does not apply.

| Situation | File |
|---|---|
| An ask reports something broken, or a fix did not hold | `bugs.md` |
| An ask has two valid shapes, two asks conflict, or a suggestion would break existing behavior | `decisions.md` |
| A unit adds or changes tests; the hygiene pass before the PR | `tests.md` |
| An ask changes pages, components, styles or interaction | `frontend.md` |
| An ask is too big for one builder, has unknowns, changes an interface others use, or the prompt has over 15 asks | `large.md` |
| An ask depends on a library, API or behavior not yet checked here | `research.md` |
| The review returns findings | `repair.md` |
| Writing the review brief (the reviewer also loads it) | `review.md` |
| Before the final message, PR and cleanup | `finish.md` |

## 3. Decide what needs a plan

Plan only for novelty, never for size:
- No plan: copy, labels, colors, fonts, spacing, small bug fixes, renames, refactors with a clear target, test cleanup, docs. Twenty of these are still no plan.
- Plan: a new page, feature or capability whose shape is a real choice (data model, state, routing, UX flow). Mark the ask `| plan`.

A planned ask gets a short spec written by its own builder as its first step (put "write a 10-line spec in your report first, then build it" in its brief). Only a large or risky feature gets a separate planner agent and a critic, and only that ask waits for them; every other ask keeps running.

## 4. Units and waves

Pack asks into units, one builder each:
- Asks that edit the same file go in the same unit, or the later one depends on the earlier.
- Tiny asks in one area go in one unit; never one agent per one-line edit.
- An ask that needs another's output (a page that uses a new shared component) depends on it.
- Aim for 3 to 6 units at once. A unit should take a builder 5 to 20 minutes.

Run the whole dependency graph in ONE Workflow script, started in the same turn you finish the ledger:

```js
const pill = agent(briefA6, { label: 'A6 pill', agentType: 'orchestra:builder' })
const others = [briefA1, briefA2, briefA4].map((b, i) => agent(b, { label: 'u' + i, agentType: 'orchestra:builder' }))
const alerts = pill.then(() => agent(briefA10, { label: 'A10 alerts', agentType: 'orchestra:builder' }))
return await Promise.all([pill, ...others, alerts])
```

Dependent units start the moment their inputs finish, inside the script, so nothing waits for a whole wave. Start the Workflow within your first few minutes: read only what you need to write the briefs; builders read the rest themselves.

Order matters: write the ledger, then start the Workflow, and only then do your own small edits. Never do your own unit before the Workflow is running; every second before dispatch delays every builder. While the Workflow runs, do one independent unit yourself (often docs or a small cluster). Then end your turn with one status line (which units are running, and that you resume on your own when they finish): the Workflow's completion wakes you. Never use ScheduleWakeup, Monitor or sleep to wait for your own background work, and never poll it. If you are woken and one unit has run more than twice its expected time, read its transcript; stop and redo it smaller rather than waiting.

Builders share your checkout when their files are disjoint: no worktrees, no extra installs. Only when two running units must edit the same file, run one of them through the Agent tool with `isolation: "worktree"` and merge its branch when it returns. Each builder commits its own unit with explicit paths when its checks pass, so finished work never waits for a slow sibling.

A builder brief holds: the ask text in the user's words, the exact files it owns, files it must not touch, what it can rely on from units before it, the checks to run, its time cap (default 15 minutes), and the plugin's `lean.py` path for bounded commands. It also holds every cross-cutting rule from the prompt (an ask that says "wherever", "everywhere", "all" or "every", such as an arrow on every price change or a format for every date), so new code in other units follows it too; name the shared helper that implements the rule, and make the unit that builds it a dependency. Builders only fix check errors in their own files; errors in a sibling's file mid-edit are expected.

## 5. Self-check, then one review

Each builder checks its own work against its ask before it reports. There is no review per unit.

When every unit has landed, in this order and as parallel as it allows:
1. Run `python3 <plugin>/scripts/lean.py check --base <base>` (a few seconds; it lists oversized files that grew, weakened tests, self-mocks, debug leftovers, rule-file and sensitive changes, secrets). Then start the review at once, in one Workflow: split the changed files into 2 or 3 groups by area (one reviewer for the whole diff only when it is under about 300 lines). Each `orchestra:reviewer` reviews its group and reads the rest of the diff only for the seams. Give each the ask ledger as the spec, the check output, the absolute path of `references/review.md`, and the lenses in it that apply.
2. While the reviewers work, run the project's full checks once (typecheck, lint, tests, build), each bounded: `python3 <plugin>/scripts/lean.py run 300 -- npm test`, and do test hygiene (below) and the docs.
3. Repair per `repair.md`: check each finding against the code, fix every real one a user or maintainer would hit (notes too when small), reject wrong ones with evidence.
4. One re-review of only the repair diff and only the raised findings; run the full checks again while it works. Whatever it says, you are done reviewing; list any new notes in the final message instead of starting another round.

If no independent reviewer can run, say so in the final message: the work is unreviewed. Your own checks never count as the review.

## 6. Test hygiene before every PR

One cleanup unit per `tests.md`: remove duplicate, skipped and implementation-detail tests, replace markup snapshots with behavior checks, remove suppressions without a reason. A failing test is fixed, never silenced. Never add tools unasked.

## 7. Finish

Push the branch and open a PR when the remote is GitHub (a plain git remote: push only). Merging into the default branch is the one step only the owner takes. Deleting stale worktrees and branches you created is part of finishing.

Final message (see `finish.md`): the user reads only your last message, so it stands alone; never write "see above". It holds the ledger as a short table (ask, status, one-line note), a "Decisions" list (each choice you made without asking, each conflict between asks and how you settled it, each suggestion you adapted and why), every answer the user asked for in full (a bug's cause, where something now lives), the check results with exit codes, and the PR or branch.

## /goal

When the user sets a goal, the Stop hook keeps you working until every ledger line is `[x]` or `[~]` and the branch is pushed. Do not stop to ask; decide per `decisions.md` and list each decision in the final message. If only the owner can unblock you, run `lean.py goal stop REASON`.
