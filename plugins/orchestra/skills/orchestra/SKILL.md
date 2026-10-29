---
name: orchestra
description: Deliver a multi-request prompt fast by running every independent ask in parallel, then one independent review. Use whenever a prompt holds more than one ask (several changes, fixes, features, docs or tests), or when the user selects Orchestra or /goal. For the main session only; never loads in a subagent.
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

## 2. Decide what needs a plan

Plan only for novelty, never for size:
- No plan: copy, labels, colors, fonts, spacing, small bug fixes, renames, refactors with a clear target, test cleanup, docs. Twenty of these are still no plan.
- Plan: a new page, feature or capability whose shape is a real choice (data model, state, routing, UX flow). Mark the ask `| plan`.

A planned ask gets a short spec written by its own builder as its first step (put "write a 10-line spec in your report first, then build it" in its brief). Only a large or risky feature gets a separate planner agent and a critic, and only that ask waits for them; every other ask keeps running.

## 3. Skills: load only when the situation applies

Orchestra's skills hold the lessons of earlier versions. Each loads only in its situation; a routine unit loads none, because every loaded rule costs time. When a situation applies to a unit, write "Load `orchestra:<skill>` first" in that unit's brief; load it yourself when it applies to your own work.

| Situation | Skill |
|---|---|
| A bug whose cause is not known yet, or a fix that did not hold | `orchestra:diagnose` |
| Two asks contradict, an ask has two valid product shapes, a suggestion would break existing behavior, the owner asks to be grilled or interviewed, wants a prototype, a term defined or renamed, a decision recorded as an ADR, or a questionnaire for someone else | `orchestra:decide` |
| A new interactive component (dialog, menu, drawer, form, keyboard flow) or an accessibility ask | `orchestra:frontend-proof` |
| An ask too big for one builder in about 20 minutes, with unknowns, an interface other units use, a long or overnight run, a context near its limit, the owner asks for a handoff document or to hand the work to a fresh background agent (read its `references/handoff.md`), or the owner asks to triage issues or PRs (read its `references/triage.md`) | `orchestra:large-work` |
| Tests that keep failing for unclear reasons, or the test hygiene pass on a large diff | `orchestra:test-quality` |
| Opening, updating or fixing a pull request: red CI, review comments, merge conflicts, a PR that must be easy to review, or the owner asks to set up pre-commit hooks or git guardrails | `orchestra:ship` |
| A flow with many states and events (booking, payments, sync, multi-step forms), no way to run and drive the real app, a unit changes a flow, route, command or UI that the repo's existing driver covers, or the owner asks to audit or update the driver | `orchestra:verify` |
| The owner corrects a mistake, or asks how something works, where new code belongs or why code is the way it is | `orchestra:diagnose` (correct mode) or `orchestra:investigate` |
| The owner asks for architecture or refactor opportunities with no diff | `orchestra:investigate` (survey mode), then `orchestra:decide` for the chosen one |
| The owner asks to review a branch or PR since a ref | `git rev-parse` the ref, make sure the diff is not empty, take the spec from issue refs in commit messages or ask, then run the §5 review with it |
| The owner asks for a deep, adversarial, thermo or "challenge this" review | two or three `orchestra:reviewer` in parallel, one with `model: "sonnet"`, with the red-team and cleanliness lenses; give each a scratch folder outside the repo for repro scripts, rerun each finding's command yourself, and keep only findings a run proves, merged by root cause |
| The owner asks for an arena or several candidate designs, or one attempt at a hard-to-reverse artifact would lock in its shape | `orchestra:large-work` `references/spikes.md`, Candidate designs |
| The owner asks what a change could break, or an ask asserts a fact about existing code ("make X public", "X already handles Y") | read `orchestra:review` `references/blast-radius.md` and prove the fact before planning |
| The owner asks for a spec, PRD or tickets | `orchestra:planner` (PRD, product or ticket mode) |
| You or a builder measure a speed, size or score, or report a speedup | read `orchestra:review` `references/measurement.md` before reporting the number |
| The owner asks for a retro, or a step only a person can take (credentials, CI secrets, a dashboard, a cutover) | `references/finish.md` (beside this skill), its retro or wizard section |

Retro: after a bug fix or an owner correction, name the check that would have caught it (a test, a lint rule, a scan rule) and add it in the same change.

Each agent also has its own role skill (`orchestra:build`, `review`, `plan`, `critique`, `investigate`, `operate`) and loads it only in the cases its agent file names.

## 4. Units and waves

Pack asks into units, one builder each:
- Asks that edit the same file go in the same unit, or the later one depends on the earlier.
- Tiny asks in one area go in one unit; never one agent per one-line edit.
- An ask that needs another's output (a page that uses a new shared component) depends on it.
- Aim for 3 to 6 units at once. A unit should take a builder 5 to 20 minutes.

Pick the agent for each unit by its kind:

| Unit | Agent |
|---|---|
| A normal build | `orchestra:builder` (Sonnet) |
| One uniform change across many files: a rename, an import or token swap, one pattern applied everywhere | `orchestra:builder-mechanical` (Haiku) |
| A refactor that reshapes types, interfaces or module boundaries | `orchestra:planner` in sketch mode, then a builder against the sketch |
| Enforce module boundaries or set up an import-boundary lint | `orchestra:builder` with "Lever mode" in the brief |
| A new internal API replaces an old one | `orchestra:builder` with "Migrate mode" in the brief: the new form, every caller, and the old form deleted in the same unit |
| A new feature whose shape is a real choice | `orchestra:planner` first (and `orchestra:critic` only when large or risky), then a builder |
| You cannot tell from a quick grep which files an ask touches | `orchestra:investigator` (Haiku) |
| The work depends on a library or API not yet checked here | `orchestra:investigator-research` (Sonnet) |
| One independent unit while the Workflow runs | you |

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

## 5. Self-check, then one review before the PR

Each builder checks its own work against its ask before it reports. Put these first-time-right checks in every brief they apply to: a change asked for "all" or "every" lands in every sibling place (find them with grep, list them in the report); a UI change holds in each theme and viewport the app has; a computed value stays inside its stated bounds and agrees with its label; a list or chart respects its stated window, one row per real entity; a multi-rule flow has one check per rule; a later correction in the prompt ("wait, no") overrides the earlier sentence; work the owner already approved runs without asking again. There is no review per unit: the review loop below runs once, after all units have landed, before the PR. You never review yourself.

When every unit has landed, in this order and as parallel as it allows:
1. Run `python3 <plugin>/scripts/lean.py check --base <base>` once (a few seconds). Then start the review at once, in one Workflow. Under about 300 changed lines: one `orchestra:reviewer-light`. Larger: split the changed files into 2 or 3 groups by area, one `orchestra:reviewer` (Opus) each, which reads the rest of the diff only for the seams. When the scan lists size, test-weakened, self-mock or rules items, add one `orchestra:reviewer-standards` with that output. Name in each review brief every lens the diff shows a risk for: types (a new type, interface or optional field, or a new `any`, `as` or `!`), boundaries (input parsing, jobs, retries, webhooks, migrations), blast-radius (a changed export, shared module or wire format), architecture-depth (a new module or layer), cleanliness (every diff), security (sensitive or secret items) and tests (test-weakened or self-mock items). Give each reviewer the ask ledger as the spec and the scan output; reviewers do not rerun the scan.
2. While the reviewers work, run the project's full checks once (typecheck, lint, tests, build), each bounded: `python3 <plugin>/scripts/lean.py run 300 -- npm test`, and do test hygiene (below) and the docs. When the full checks take more than about 3 minutes, give them to `orchestra:operator` (Haiku) in the review Workflow instead. On a diff over about 800 lines, give the hygiene pass to `orchestra:builder-cleanup` (Haiku) after the repairs.
3. Check each finding against the code. Fix every real finding a user or maintainer would hit, notes included when the fix is small; do not leave it for later. When a finding is disputed or a repair did not hold, read `references/repair.md` (beside this skill). Send them to one repair builder (or one per disjoint file group, in parallel), or fix a few small ones yourself.
If no independent reviewer can run, report BLOCKED: independent review. Never count your own review or green checks as the verdict.
4. Re-review only the files the repair touched and only the raised findings, by the reviewer agent that raised them; run the full checks again while it works. Repeat repair and re-review until CLEAN, at most 3 rounds. A finding that survives 3 rounds goes to one repair by the Agent tool with `model: "opus"`, then one last re-review. List new notes in the final message instead of starting another round.

Before the final message, compare it with the ledger: never report done while a line is open, and name each thing left. Remove what you created and no longer need (scratch files, debug flags, worktrees, branches, test data).

## 6. Test hygiene before every PR

Keep tests few, fast and behavior-level. In the changed area and the suite:
- remove duplicate tests and tests of implementation details or mocks;
- delete or fix every skipped test; no stale skip reasons;
- replace brittle snapshots of markup with a behavior assertion;
- remove lint suppressions without a reason, or fix the code;
- a failing test is fixed (code or test), never silenced or excepted;
- every new module gets the smallest test that proves its behavior;
- on every diff, remove slop per `orchestra:build` `references/cleanup.md` "Slop to remove": comments that restate the code, defensive checks on trusted paths, casts that only silence types.
Use fast native tools if the repo already has them (oxlint, tsgo, tsrs); never add tools unasked.

## 7. Finish

Push the branch and open a PR when the remote is GitHub (a plain git remote: push only). Merging into the default branch is the one step only the owner takes. Deleting stale worktrees and branches you created is part of finishing.

When a unit failed, an ask was dropped or you open a PR, read `references/finish.md` first. Final message: the user reads only your last message, so it stands alone; never write "see above". It holds the ledger as a short table (ask, status, one-line note), every answer the user asked for in full (a bug's cause, a choice you made, where something now lives), the check results, and the PR or branch.

## /goal

When the user sets a goal, the Stop hook keeps you working until every ledger line is `[x]` or `[~]` and the branch is pushed. Do not stop to ask; settle choices with `orchestra:decide` and list each decision in the final message. If only the owner can unblock you, run `lean.py goal stop REASON`.
