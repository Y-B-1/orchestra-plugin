# Orchestra 2.5 design: route by diff size, not item count

Status: draft for owner decisions (D1 to D5). No code until they are settled.

## Problem

2.4 routes on the number of items in the request (`start --items N`: 1 to 5 inline, 6 or more through a plan card and Workflow builders). The item count is a poor signal:

- Ten typo fixes go to a designer-planner and parallel builders. One "add auth" item runs inline with no design step.
- Six or more items start with a plan. Matt Pocock's rule (post of 2026-10-08) is the opposite: never start with the map; escalate to one only when alignment shows the work is bigger than expected.
- The count decides nothing about speed. Parallelism pays only when there are 2 or more independent units, each large enough to cover an agent's fixed start cost.

The end of a 2.4 run already uses the diff: pre-PR review lenses come from the actual diff. 2.5 makes the start of the run use the diff too.

## Evidence the design rests on

- 2.3 benchmark (3 one-line edits): 3 builders used 190,942 tokens, about 64K each for a one-line change. That is the fixed cost of one worker agent.
- 2.4 benchmark (same edits): 1 reviewer, 35,990 tokens; edits inline. 93% fewer sub-agent tokens.
- So a worker earns its start cost only when its unit of work is clearly larger than about 40K to 60K tokens of work, or when it runs beside other work and saves wall time the owner wants.
- `mattpocock/skills@49dd158 skills/engineering/wayfinder/SKILL.md`: a map of decision tickets for work larger than one session. Research tickets are worked by parallel subagents; human decision tickets (grilling) one per session. The map stops when no fog remains, then work is handed off to build.
- Grilling is human-in-the-loop. A subagent cannot ask the owner questions mid-task, so alignment runs in the main session, never in a worker.

## Two separate questions

2.4 mixes them into one number. 2.5 splits them.

1. **How much alignment comes before code?** Decided by the expected diff size and how much is still unknown ("fog").
2. **How is the work executed: inline, parallel workers, or both?** Decided by the number of independent units and their size, after alignment.

## Question 1: size tiers

The coordinator estimates the size at start, inline, by reading the files the work touches. When the area is unknown, it starts one `investigator-code` card (or a Workflow fan-out over several areas) to size it.

| Tier | Test (Pocock's, plus a numeric guide, D1) | Alignment | Start |
|---|---|---|---|
| tiny | The owner can review the diff at a glance and a retry costs almost nothing. Guide: up to about 50 changed lines, no interface or schema change, no open decision. | None. One-shot. Align after the diff, in review. | Inline edit. |
| medium | Fits one session and one PR. Some decisions are open. Guide: about 50 to 400 lines, or any interface change. | Grill inline in the main session: questions in frontier rounds, each with a recommended answer. Write settled terms to the glossary and hard-to-reverse choices as decision records. | Inline grilling, then question 2. |
| large | More than one session, or fog that grilling cannot clear in one sitting. | Wayfinder map (new, see below). | Never at start. Reached only by escalation from medium. |

There is no "start large" path. A request that looks large still starts with a medium grilling session. Pocock's failure mode is a map and tickets nobody needed; this rule prevents it. The one exception is when the owner explicitly asks for a map.

### Escalation

`orchestra.py route --size <tier> --reason TEXT` changes the tier mid-run and logs why (the 2.4 `route_log` stays). Triggers:

- **tiny → medium:** the edit turns out to need a decision, or the diff grows past the guide.
- **medium → large:** grilling goes past the context ceiling (40% to 60% of the window), or answers keep opening new questions faster than they close them.

### Size check against the real diff (D2)

The engine records the run's base commit (2.4 already does). Before the pre-PR review, the engine measures `git diff --shortstat <base>..<candidate>` and compares it with the declared tier. If the real diff is over the tier's guide and no escalation is logged, the pre-PR step refuses (or warns, D2). The fix is one `route` command with a reason. This keeps the declared size honest without asking the coordinator to predict perfectly.

## Question 2: execution

After alignment, the coordinator splits the settled work into **units**. A unit is a set of files that change together; units that share a file merge into one (2.4 rule S11). Then each unit gets an executor:

| Situation | Executor | Why |
|---|---|---|
| Only tiny units, any number | Main session, one inline pass, one commit, one review. | No agent start cost. Fastest for small work. This is the 2.4 benchmark path. |
| 1 unit that is not tiny | Main session, inline. | No parallelism to gain. A worker would add its start cost and nothing else. |
| 2+ independent units that are not tiny | Workflow: one builder per unit, worktrees only for concurrent writers. The main session takes one unit inline beside them (inline reservation, 2.4 feature). | Wall time drops to the slowest unit. Each unit covers its start cost. |
| Main-session context near the ceiling | Delegate the remaining units even if there is only one. | Protects the coordinator's context. Your global rule sets the ceiling at 40% to 60%. |
| Mixed tiny and larger units | Workflow builders for the larger units; the main session does the tiny ones inline while they run. | Speed and tokens both. |

The engine no longer forces a route from a count. It checks only:

- A builder dispatch with a not-tiny unit needs no helper reason. A builder dispatch for a tiny unit needs `--helper REASON` (keeps the 2.4 brake on wasting an agent on trivial work).
- A plan card (designer-planner, plan mode) needs the run to be `large`, or an owner request.

## Where Workflow is most valuable

Workflow runs 2 or more agents in parallel from one script. 2.5 uses it in four places and nowhere else:

1. **Sizing an unknown area:** parallel `investigator-code` agents, one per area, each returns a size estimate and the files it found. Haiku, cheap.
2. **Clearing fog (large only):** all research tickets on a wayfinder map run at once as `investigator` agents. Pocock's wayfinder does the same.
3. **Building:** independent, not-tiny units, one builder each.
4. **Review:** more than one lens only when the diff earns it (2.4 rule: lenses derived from the diff). A tiny diff gets one reviewer (D3).

## Wayfinder in Orchestra (large tier)

New reference: `orchestra/references/wayfinder.md`, adapted from Pocock's skill (MIT, credited in THIRD-PARTY-NOTICES and SKILL-SOURCES).

- **Map:** destination, notes, decisions so far (one line each, linking the ticket), not yet specified (fog), out of scope. Home is set by D4.
- **Decision tickets, not build slices.** Types: research (AFK, parallel investigator), prototype (with the owner), grilling (with the owner, main session), task (unblocks a decision).
- **One human decision ticket per session.** Research tickets have no such limit and run together.
- **Hand-off:** when no fog remains, the map becomes the input of a designer-planner plan card (the existing plan mode, which already slices vertically), and the build follows question 2.
- **Across sessions:** the map is the handoff artifact. A new session reads the map, not the old transcript (fits your rule of one ticket per session and state on disk).

The existing designer-planner product and design modes remain for written specs. Grilling itself always happens in the main session.

## What stays from 2.4

- Inline-first; builder self-review; one independent pre-PR review; one repair, one re-review, then hold.
- Lenses derived from the actual diff; gate receipts; the guard, including the subagent guard.
- Minimum worktrees (S11); inline reservations beside workers.
- 2.4 states with `items` keep loading and keep 2.4 routing, as 2.3 states did in 2.4.

## What changes

| Area | 2.4 | 2.5 |
|---|---|---|
| Start | `start --items N` required | `start --size tiny\|medium\|large` required; `--items` accepted only from a 2.4 state |
| Mid-run | `route --items N --reason` | `route --size <tier> --reason` |
| Plan card | 6 or more items | Large tier, or an owner request |
| Builder dispatch | Inline route needs `--helper` for any builder | Only a tiny unit needs `--helper` |
| Pre-PR | Lenses from the diff | Plus the size check against the declared tier (D2) |
| Large work | No multi-session structure | Wayfinder map |

## Open decisions for the owner

- **D1. Tier guide numbers.** Recommended: tiny up to 50 changed lines with no interface change; medium up to 400; above that, or more than one session, is large. The qualitative test comes first; the numbers only drive the check in D2.
- **D2. Real diff over the declared tier.** Recommended: refuse the pre-PR step until a `route --size` escalation is logged. One command fixes it, and the log shows where estimates go wrong.
- **D3. Review for a tiny diff.** Recommended: keep one independent reviewer, but on Sonnet 5.5 medium instead of Opus. Independence is a project rule; a tiny diff does not need the Opus model.
- **D4. Home of the wayfinder map.** Recommended: a local markdown file in the repo (`docs/maps/<name>.md`), with the GitHub issue tracker as an option. Local works offline, in any repo, and costs no API calls.
- **D5. Agent start cost threshold.** Recommended: no fixed number in the engine. The coordinator delegates a unit when it is not tiny and either runs beside other work or protects the context ceiling. A number would need a token estimate the coordinator cannot make reliably.

## Acceptance (for the plan that follows the decisions)

1. `start` without `--size` on a new run exits non-zero and names `--size`.
2. `start --size large` on a new run exits non-zero unless `--owner-request` is passed; the message names escalation.
3. A tiny run whose candidate diff exceeds the D1 guide is refused (or warned, D2) at the pre-PR step until `route --size` logs a reason.
4. A builder dispatch for a unit marked tiny without `--helper` exits non-zero; for a medium unit it succeeds.
5. A 2.4 state with `items` loads and keeps 2.4 routing; a 2.3 state still loads.
6. The 2.4 benchmark task (three tiny edits) runs with 0 builders and 1 reviewer, and uses no more sub-agent tokens than 2.4 (35,990).
7. A two-unit medium benchmark, with disjoint files, runs the units in parallel and finishes faster than the same work run serially.
