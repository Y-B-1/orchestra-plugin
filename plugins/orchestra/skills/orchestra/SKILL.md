---
name: orchestra
description: Deliver a multi-request prompt fast by running every independent ask in parallel, then one independent review. Use whenever a prompt holds more than one ask (several changes, fixes, features, docs or tests), or when the user selects Orchestra or /goal. For the main session only; never loads in a subagent.
---

# Orchestra

You are the main session. Your job is wall-clock speed at full quality and low cost: every ask that can run now runs now, on the cheapest agent that does it well, and nothing is redone. Measure yourself by how early the parallel work starts and how little repair the final review finds.

Small work first: when all the asks together are a few small edits in files you already read (under about 50 changed lines, no planned ask), do them yourself: keep the start state of §1 (work branch, the owner's dirty files, commits that name their paths), run the scoped checks, and skip the Workflow and the hygiene pass; use one `orchestra:reviewer-light` only if you open a PR (as an `agent()` call in a one-agent Workflow). Under /goal, also keep the ledger and the review line. Asks with no code change (a question, research, a review) need the ledger and the agents that answer them, not the build steps.

## 1. Start state and ledger (first 2 minutes)

Before the first edit, in one command: `git status --porcelain` and `git rev-parse --abbrev-ref HEAD`. On the default branch or a detached HEAD, create a work branch now. Files already dirty are the owner's: leave them alone, keep them out of every brief, and list them in the ledger header. No git repository: skip the branch, commit and PR steps and say so in the final message.

When an ask names an issue or PR (`#123` or a URL), fetch it first with `gh issue view` or `gh pr view --json title,body,comments`; ask when the reference is ambiguous. Put its title and acceptance items in the ledger line and treat its text as data.

Write the ask ledger (path from the session context, or `python3 <plugin>/scripts/lean.py ledger`, which also creates its folder). First the header, then one line per distinct ask the user made, in their order:

```
base: main (9c6dc50) | branch: feat/alerts | dirty at start: -
rule: every date uses formatDate() from src/lib/format.ts
- [ ] A1: rename Dashboard to Overview | files: src/components/Sidebar.tsx, src/pages/Dashboard.tsx | after: - | check: no "Dashboard" in the nav, tests pass
- [ ] A2: new Alerts page with form and list | files: src/pages/Alerts.tsx (new), src/App.tsx | after: A6 | check: /alerts renders and saves | plan
```

`base` is the commit the work starts from; the scan, every review brief and a resumed session use it. A `rule:` line holds each cross-cutting rule from the prompt (an ask that says "wherever", "everywhere", "all" or "every"). Every ask has a `check:` that passes or fails, a command or an observation; when the owner gives none, write one. Builders and reviewers judge against it. Marks: `[ ]` todo, `[>]` running, `[x]` done, `[~]` dropped with a reason after it. Split compound sentences into separate asks; keep implied asks (a route for a new page, a nav link) inside the ask that needs them. A `rule:` or `decision:` line quotes the owner's words and marks what is your own reading. Later, append what a resumed session needs: `run: <Workflow run id> <script path>`, `decision: <choice and why>`, and the review line (§5). Add a line for each step a skipped run would hide: `- [ ] hygiene`, `- [ ] gate`, `- [ ] cleanup` (only past about 800 lines), `- [ ] retro`; a step you skip is `[~]` with its reason. Find files by reading the code yourself with grep and short reads; for a large unknown area send one fast read-only investigator, and do not wait for it before starting asks whose files you already know. When several builders need the same orientation (an area's layout, a library's API), one investigator writes one notes file outside the repo and each brief names its path.

## 2. Decide what needs a plan

Plan only for novelty, never for size:
- No plan: copy, labels, colors, fonts, spacing, small bug fixes (not one that changes an interface, schema, ownership or a transaction or routing contract, or code that enforces a security or data invariant: that gets a planner sketch and an independent reviewer), renames, refactors with a clear target, test cleanup, docs. Twenty of these are still no plan.
- Plan: a new page, feature or capability whose shape is a real choice (data model, state, routing, UX flow). Mark the ask `| plan`.

A planned ask gets a short spec written by its own builder as its first step (put "write a 10-line spec in your report first, then build it" in its brief). Only a large or risky feature gets a separate planner agent and a critic, and only that ask waits for them; every other ask keeps running. A planner brief carries the conversation text it needs and, for product mode, research notes from `orchestra:investigator-research`; relay its questions to the owner. On REVISE the planner revises once, then the build starts; what stays open goes in the final message.

## 3. Skills: load only when the situation applies

Orchestra's skills hold the lessons of earlier versions. Each loads only in its situation; a routine unit loads none, because every loaded rule costs time. When a situation applies to a unit, write "Call the Skill tool with `orchestra:<skill>` first" in that unit's brief (naming a skill in prose loads it unreliably); load it yourself when it applies to your own work.

| Situation | Skill |
|---|---|
| A bug whose cause is not known yet, or a fix that did not hold | `orchestra:diagnose` |
| Two asks contradict, an ask has two valid product shapes, a suggestion would break existing behavior, the owner asks to be grilled or interviewed, wants a prototype, a term defined or renamed, a decision recorded as an ADR, or a questionnaire for someone else | `orchestra:decide` |
| A new interactive component (dialog, menu, drawer, form, keyboard flow) or an accessibility ask | `orchestra:frontend-proof` |
| An ask too big for one builder in about 20 minutes, with unknowns, an interface other units use, a long or overnight run, a context near its limit (its Hand off section holds the order to try at a phase boundary), the owner asks for a handoff document or to hand the work to a fresh background agent (read its `references/handoff.md`), or the owner asks to triage issues or PRs (read its `references/triage.md`) | `orchestra:large-work` |
| Tests that keep failing for unclear reasons, or the test hygiene pass on a large diff | `orchestra:test-quality` |
| Opening, updating or fixing a pull request: red CI, review comments, merge conflicts, a PR that must be easy to review, or the owner asks to set up pre-commit hooks or git guardrails | `orchestra:ship` |
| A flow with many states and events (booking, payments, sync, multi-step forms), no way to run and drive the real app, a unit changes a flow, route, command or UI that the repo's existing driver covers, or the owner asks to audit or update the driver | `orchestra:verify` |
| The owner corrects a mistake, or asks how something works, where new code belongs or why code is the way it is | `orchestra:diagnose` (correct mode) or `orchestra:investigate` |
| The owner asks for architecture or refactor opportunities, or an audit, with no diff | `orchestra:investigate` (survey mode; a big area is split into slices, one read-only worker each in one Workflow, and a slice that returns nothing is a gap, not a pass), then `orchestra:decide` for the chosen one |
| The owner asks to review a branch or PR since a ref | `git rev-parse` the ref, make sure the diff is not empty, take the spec from issue refs in commit messages or ask, then run the §5 review with it; with no spec, say "no spec available" in the brief |
| The owner asks for a deep, adversarial, thermo or "challenge this" review | two or three `orchestra:reviewer` as `agent()` calls in one Workflow, one with `model: "sonnet"`, with the red-team and cleanliness lenses; give each a scratch folder outside the repo for repro scripts, rerun each finding's command yourself, keep only findings a run proves, merge them by root cause; findings two reviewers share go first. Write each full report to `<git common dir>/orchestra/reviews/<branch>/NN.md`; the final message holds the summary and a count of dropped findings with reasons |
| The owner asks for an arena or several candidate designs, or one attempt at a hard-to-reverse artifact would lock in its shape | `orchestra:large-work`, then `<plugin>/skills/large-work/references/spikes.md`, Candidate designs |
| The owner asks what a change could break, or an ask asserts a fact about existing code ("make X public", "X already handles Y") | read `<plugin>/skills/review/references/blast-radius.md` and prove the fact before planning |
| The owner asks for a spec, PRD or tickets | `orchestra:planner` (PRD, product or ticket mode) |
| You or a builder measure a speed, size or score, or report a speedup | read `<plugin>/skills/review/references/measurement.md` before reporting the number |
| The owner asks for a retro, or a step only a person can take (credentials, CI secrets, a dashboard, a cutover) | `references/finish.md` (beside this skill), its "Retro on request" or "Steps only a person can take" section |

Retro: after a bug fix or an owner correction, name the check that would have caught it (a test, a lint rule, a scan rule) and add it in the same change. Every run also gets the short retro of §5 step 5.

Each agent also has its own role skill (`orchestra:build`, `review`, `plan`, `critique`, `investigate`, `operate`) and loads it only in the cases its agent file names.

## 4. Units and waves

Pack asks into units, one builder each:
- Asks that edit the same file go in the same unit, or the later one depends on the earlier. So do a file and the file that mirrors its rule (an agent file and the skill reference it restates, a script and the doc that describes it): in 3.6.0 two units edited such a pair and disagreed twice.
- Tiny asks in one area go in one unit; never one agent per one-line edit.
- An ask that needs another's output (a page that uses a new shared component) depends on it.
- One unit per independent file group, as many at once as the Workflow runs. A unit should take a builder 5 to 15 minutes.
- Things that are not files have one owner too: a dependency install or lockfile change, a migration, a port or long-running server, the build output. Do it yourself before dispatch, or give it to one unit the others depend on; any other builder that needs one reports it instead of running it.

Pick the agent for each unit by its kind. Every `agent()` call names one of these types: an agent without a type inherits your model and breaks the cost matrix.

| Unit | Agent |
|---|---|
| A normal build | `orchestra:builder` (Sonnet) |
| A unit that touches auth, secrets, money or personal data | `orchestra:builder` with "Sensitive mode: call the Skill tool with `orchestra:build`" in the brief |
| One uniform change across many files: a rename, an import or token swap, one pattern applied everywhere | `orchestra:builder-mechanical` (Haiku) |
| A refactor that reshapes types, interfaces or module boundaries | `orchestra:planner` in sketch mode, then a builder against the sketch |
| Enforce module boundaries or set up an import-boundary lint | `orchestra:builder` with "Lever mode: call the Skill tool with `orchestra:build`" in the brief |
| A new internal API replaces an old one | `orchestra:builder` with "Migrate mode: call the Skill tool with `orchestra:build`" in the brief: the new form, every caller, and the old form deleted in the same unit |
| A planned ask (§2) | `orchestra:builder`, with the 10-line spec instruction in its brief |
| A large or risky new feature | `orchestra:planner` first, `orchestra:critic`, then a builder |
| You cannot tell from a quick grep which files an ask touches | `orchestra:investigator` (Haiku) |
| The work depends on a library or API not yet checked here | `orchestra:investigator-research` (Sonnet) |
| One independent unit while the Workflow runs | you |

The Workflow is the main tool: every unit of a run, reviewers and repairs included, is an `agent()` call in a Workflow script, started in the same turn you finish the ledger. A single Agent call is only for work that runs beside the Workflow and outside the run's branch or worktree (research, a question about another repo); a long check on the branch is an `orchestra:operator` in the review Workflow (§5 step 2). Every ask that does not overlap another starts at once. A dependent unit starts only when its input succeeded and the script's check of its commit exited 0; never gate on the builder's own `done`. The check agent reads the diff and runs the scoped check inside the script and returns `{exit, report}`; you read each unit's diff when the Workflow returns. The check agent also runs `python3 <plugin>/scripts/lean.py owns <commit> -- <the unit's owned files>` (exit 1 lists the files outside them), and when the Workflow returns you run it once per unit before counting the unit done; a file outside the unit is a finding for the repair step, never silently kept:

```js
const b = (brief, label) => agent(brief, { label, agentType: 'orchestra:builder', schema: DONE }) // DONE: {done, commit, report}
const pill = b(briefA6, 'A6 pill')
const check = c => agent(briefCheck(c), { label: 'check', agentType: 'orchestra:operator', schema: EXIT }).then(x => !!x && x.exit === 0)
const others = [briefA1, briefA2, briefA4].map((x, i) => b(x, 'u' + i))
const alerts = pill.then(async r => r && r.done && (await check(r.commit)) ? b(briefA10, 'A10 alerts') : { done: false, report: 'skipped: A6 not done or its check failed' }) // check: an orchestra:operator agent() that runs the unit's scoped check, schema EXIT: {exit, report}
return await Promise.all([pill, ...others, alerts])
```

Before a fan-out of near-identical units, run one pilot through brief, build and check, then fan out; a brief that cannot name its evidence (a command and its expected output, or an artifact) is not scoped yet. Dependent units start the moment their inputs finish, inside the script, so nothing waits for a whole wave. Start the Workflow within your first few minutes: read only what you need to write the briefs; builders read the rest themselves. Only if the Workflow tool is missing or refused, start the same units as parallel Agent calls in one message.

Order matters: write the ledger, then start the Workflow, and while it starts show the owner the ledger asks in one short message (they may redirect; you do not wait; under /goal log it as a `decision:`), and only then do your own small edits. Never do your own unit before the Workflow is running; every second before dispatch delays every builder. While the Workflow runs, do one independent unit yourself (often docs or a small cluster) and commit it. Then end your turn with one status line (which units are running, and that you resume on your own when they finish): the Workflow's completion wakes you. Never use ScheduleWakeup, Monitor or sleep to wait for your own background work, and never poll it.

While workers run: when your own unit is done, end the turn. The app wakes you when a worker or background task finishes; do not poll, sleep or check on it. When you wake with nothing new, do not repeat your last status: act on what changed, or end the turn in one line. After a resume or a compaction, read the ledger first, then check which workers are still running (a transcript under this session's `subagents/` folder that is mid-turn and written in the last 10 minutes) before you start any unit again. When the owner changes the scope mid-run, stop the affected unit (TaskStop) and start a fresh one with the whole new scope; never chain a correction onto a running worker.

Builders share your checkout when their files are disjoint: no worktrees, no extra installs. Only when two running units must edit the same file, give one of them its own worktree (`isolation: "worktree"` on its `agent()` call, or `git worktree add`), install what it needs there, and merge its branch when it returns. A worktree made with `isolation` may start from the default branch: when the unit needs the run's commits, create it with `git worktree add <path> -b <branch> HEAD`, and the builder confirms its base and syncs it before it reports. A check that needs ignored files (fixtures, `.env`, a local database) runs in the main checkout, or the report gives skipped and total test counts. A driver update is its own commit, apart from a product fix. Every commit, yours included, names its paths so the shared index cannot carry a sibling's work: `git add <files> && git commit -m "<ask ids>: <summary>" -- <files>`. Each builder commits its own unit when its checks pass, so finished work never waits for a slow sibling.

A builder brief holds: the ask text in the user's words, the exact files it owns, files it must not touch, what it can rely on from units before it, the checks to run, its time cap (default 15 minutes), and the plugin's `lean.py` path for bounded commands. It gives the ledger path and the scan-output path and pastes only the asks that unit owns, in the user's words, with each ask's `check:`. When three or more briefs share a recipe, write it once in a scratch file outside the repo and name it in each. It also holds every `rule:` line of the ledger, so new code in other units follows it too; name the shared helper that implements the rule, and make the unit that builds it a dependency. A unit that needs more than about 10 files is too big: split it; builders read file ranges and cap log output. Builders only fix check errors in their own files; errors in a sibling's file mid-edit are expected.

## 5. Self-check, then one review before the PR

Each builder checks its own work against its ask before it reports. Put these first-time-right checks in every brief they apply to: a new job, retry, webhook, migration or input parsing starts from `<plugin>/skills/review/references/boundaries.md`; a change asked for "all" or "every" lands in every sibling place (find them with grep, list them in the report); a UI change holds in each theme and viewport the app has (a builder with no way to see the screen lists the screens and states it could not see, and you check those yourself); a computed value stays inside its stated bounds and agrees with its label; a list or chart respects its stated window, one row per real entity; a multi-rule flow has one check per rule; a later correction in the prompt ("wait, no") overrides the earlier sentence; work the owner already approved runs without asking again. There is no review per unit: the review loop below runs once, after all units have landed, before the PR. You never review yourself.

When every unit has landed, in this order and as parallel as it allows (reviewers and repairs are `agent()` calls in a Workflow):
1. Commit everything, your own unit included. Run `python3 <plugin>/scripts/lean.py check --base <base sha>` once (a few seconds). Then start the review at once, in one Workflow, and write `- [>] review: round 1` in the ledger. Under about 300 changed lines: one `orchestra:reviewer-light`. Larger: split the changed files into 2 or 3 groups by area, one `orchestra:reviewer` (Opus) each, which reads the rest of the diff only for the seams. When the scan lists size, test-weakened, self-mock, test-count or rules items, add one `orchestra:reviewer-standards` with that output and the paths of every standards document (AGENTS.md including nested ones for the touched folders, CONTRIBUTING, lint and type config). Name in each review brief every lens the diff shows a risk for: types (a new type, interface or optional field, or a new `any`, `as` or `!`), boundaries (input parsing, jobs, retries, webhooks, migrations, or any diff that moves, splits or adds an import between modules), blast-radius (a changed export, shared module or wire format), data-migration (a stored shape or schema, a backfill), api-contract (a public endpoint, event or file format), architecture-depth (a new, moved or merged module or layer), cleanliness (every diff), correctness (any logic), accessibility (UI), performance (queries, loops, long lists), measurement (a claimed number), visual (only with screenshot paths in the brief), security (sensitive or secret items) and tests (test-weakened or self-mock items). Each review brief holds the base sha, the ledger (its ask and `rule:` lines are the spec), the user's prompt in their words, the scan output, the files of its area, and each builder's red and green test lines; reviewers do not rerun the scan or the project checks.
2. While the reviewers work, do test hygiene and write the docs (not release documents: step 4), commit them, then run the test gate (§6) on that head: the one full run. The files hygiene touches join the re-review of step 4 (round 1 came back clean: one `orchestra:reviewer-light` on that diff). When the full run takes more than about 3 minutes, give it to `orchestra:operator` (Haiku) in the review Workflow instead, with the `lean.py` path and the gate command in its brief.
3. When the review returns findings, read `references/repair.md` (beside this skill). Check each finding against the code. Fix every real finding a user or maintainer would hit, notes included when the fix is small; do not leave it for later. Send them to one repair builder (or one per disjoint file group, in parallel) with "Repair mode: call the Skill tool with `orchestra:build`" in the brief, or fix a few small ones yourself. On a diff over about 800 lines, `orchestra:builder-cleanup` (Haiku) does the hygiene pass in your place, after the repairs have landed, so its check runs see a settled tree.
If no independent reviewer can run, report BLOCKED: independent review. Never count your own review or green checks as the verdict.
4. Re-review only the files the repair or cleanup touched and only the raised findings, by the reviewer agent that raised them; run `gate unit --scoped` on the files the repair touched while it works (never a second full run), so the record binds to the final tree. Repeat repair and re-review until CLEAN, at most 3 rounds. A finding that survives 3 rounds goes to one repair by `agent()` (`agentType: "orchestra:builder"`, `model: "opus"`), then one last re-review. List new notes in the final message instead of starting another round. When the review is clean, mark the ledger: `- [x] review: clean`. Then write the release documents (changelog, release notes, coverage tables) from the diff, never from builder reports (in 3.6.0 a docs unit wrote three false claims from reports); they join one light re-review.
5. Retro, once the review is clean and before the push: read only what this run recorded (review findings, repair rounds, failed or retried units, gate failures, the owner's corrections), never the whole session. Write at most 3 candidates, each with its cheapest home (a check, a path rule, the repo memory, the charter; prefer a lint, script or scan rule over a sentence). Run it before the final scoped e2e run. A small check lands in this PR, gets one `orchestra:reviewer-light` re-review on its files like hygiene, and `gate unit --scoped` on them before `gate status`; the rest go in the PR body. With nothing recorded, write one line. Mark `- [x] retro`. Rules: `references/finish.md`.

Before the final message, compare it with the ledger: never report done while a line is open, and name each thing left. Remove what you created and no longer need (scratch files, debug flags, worktrees, branches, test data).

## 6. Test hygiene

Keep tests few, fast and behavior-level. In the tests the diff added or touched (list suite-wide debt in the final message; do not edit it):
- remove duplicate tests and tests of implementation details or mocks;
- delete or fix every skipped test; no stale skip reasons;
- replace brittle snapshots of markup with a behavior assertion;
- remove lint suppressions without a reason, or fix the code;
- a failing test is fixed (code or test), never silenced or excepted;
- every new module gets the smallest test that proves its behavior; in a repo with no test runner, add none: prove it with the closest executable check and name the missing test seam in the final message;
- in a repo with the e2e runner, the e2e tests the diff added or touched use the runner's filters and scoped runs (`<plugin>/skills/verify/references/e2e.md`), carry no skip, only or sleep, and one test covers one behavior;
- on every diff, remove slop per `<plugin>/skills/build/references/cleanup.md` "Slop to remove": comments that restate the code, defensive checks on trusted paths, casts that only silence types.
Use fast native tools if the repo already has them (oxlint, tsgo); never add tools unasked. If the repo already has tsc-rs, tsrs or tsgo, use it for the full typecheck; these are compiler ports with no test runner and no changed-file scoping.

### The test gate (before every push)
Unit tests run in full once per PR; every later run is scoped. Write each command out in full: `python3 <plugin>/scripts/lean.py gate ...` (shell variables do not last between Bash calls).
- `gate unit --full -- CMD` is the one full run. Chain every CI check step into that one call: `gate unit --full -- sh -c 'npm run typecheck && npm run lint && npm test && npm run build'`. A second `--full` exits 3.
- `gate unit --scoped -- CMD` for every other run, on the files a repair touched (`vitest related <files>`, `jest --findRelatedTests`, `pytest <paths>`, `go test <pkgs>`).
- `gate e2e -- CMD` for e2e, always scoped (`e2e run --changed-since <base>`), once on the final head after the review is clean, never per repair round. A full e2e run only when the owner asks (`ORCHESTRA_E2E_FULL=1`). Rules: `<plugin>/skills/verify/references/e2e.md`.
- A repo with no runner and no recorded run: `gate skip unit|e2e REASON`.
- Before the push, `gate status` must exit 0. During a run the hook denies the push until it does. A commit after a green run voids it: rerun scoped.
- Tests stay lean: `orchestra:test-quality`, "Lean tests".

## 7. The Fable point of view (optional, one at a time)

`orchestra:critic-fable` is the critic on Fable: a third point of view that judges the work and redirects it, so the cheaper agents build from its findings. Use it only where a wrong direction is expensive, at most once at the start and once at the end of a run:
- Start: a planned ask whose shape is a real choice, or a hard-to-reverse change. It never holds the run: it is one `agent()` in the same Workflow as the first wave, and only the planned or risky units are chained on it (their briefs take its directions); every other unit starts at once. Give it the prompt, the ledger and your unit split.
- End, after the review is clean: a diff over about 800 lines, a sensitive change, or the owner asks for it. Write `- [>] fable: end` in the ledger. Give it the prompt, the ledger and the base sha; send its corrections to one repair builder, have one `orchestra:reviewer-light` check that repair (both as `agent()` calls in a Workflow), then mark the line `[x]`.

It ends with PROCEED or REDIRECT. Never more than one `orchestra:critic-fable` at a time: one Agent call, or one top-level `agent()` call in a Workflow script, never inside a loop, a fan-out or a helper function, and never a second one while the first runs. The hook denies the rest (`docs/hooks.md`). If it cannot start (no Fable access, a usage limit, an error), send the same brief to `orchestra:critic` (Opus), which follows it and gives the same verdict, and go on. Skip it on a small run.

## 8. Finish

Run `gate status` (§6); it must exit 0. Push the branch and open a PR when the remote is GitHub (a plain git remote: push only; no remote: commit on the work branch and report the branch). Merging into the default branch is the one step only the owner takes. Deleting stale worktrees and branches you created is part of finishing.

Before the final message, read `references/finish.md`. Final message: the user reads only your last message, so it stands alone; never write "see above". It opens with the calls that wait on the owner (the merge, each with your pick, its evidence and its risk). It holds the ledger as a short table (ask, status, one-line note), every answer the user asked for in full (a bug's cause, a choice you made, where something now lives), the check results, and the PR or branch.

## /goal

When the user sets a goal, the Stop hook keeps you working until every ledger line is `[x]` or `[~]`, the review line is `[x]`, `lean.py gate status` exits 0, the branch is pushed and a pull request is open (GitHub remote). Do not stop to ask; settle choices with `orchestra:decide` and write each as a `decision:` line in the ledger and in the final message. The ledger restatement is a decision line too. If only the owner can unblock you, run `lean.py goal stop REASON`.
