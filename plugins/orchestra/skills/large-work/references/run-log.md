# Long runs, hypothesis loop and decision log

## Frame before a long run
State before any code:
- Done as a falsifiable predicate (a command and its expected result).
- Scope with numbers: units, effort, the blockers found while reading.
- Rigor, biased high. One-way doors and wide blast radius get more gates and artifacts; reversible low-stakes steps get fewer.
Show the framing once and get one checkpoint before a multi-hour run. Reversible work proceeds.

## Design the run
- Split into atomic units that land on their own. Order the riskiest unknown first.
- Build the check before the work and capture the baseline from the pre-change state, so the check reads "old value vs new value".
- Fan out only across seams, each worker in its own worktree or branch. Do not fan out what one script can do in one pass.
- Write the phase list down. That list is what the owner reviews.

## Loop per unit
Each unit is an experiment: state the hypothesis, make the smallest change, measure against the predicate on the real artifact. Keep it if it advanced, revert it if not.
- Inspect the artifact, never a self-report. When a check passes too easily, suspect the observation method before the system.
- A verdict is VERIFIED, NOT VERIFIED or INCONCLUSIVE. Inconclusive is not a pass. Never hide a negative.
- If a worker games the gate, reset and harden the contract. If the gate is wrong, fix it in its own change.
- A comparison tool needs a seeded known-bad change for each thing it claims to compare, and must report missing input as inconclusive, never as a match.
- At the end, check the whole against the predicate on the real product, not only the harness. Turn a recurring correction into a check or script.

## Decision log
Use for long, unattended or multi-phase runs. One TSV file, one row per decision, append-only: `.audit/<task-slug>.tsv`, or `decisions.tsv` in the work folder. Leave it out of git unless a reviewer needs the trail to trust the result; then commit it.
Columns: ts (ISO 8601), phase, decision (one line), why (plain words), evidence (commit SHA, PR, `file:line` or artifact path, never prose), result (`tests green`, `reverted`, `INCONCLUSIVE`, `open`).
- Log forks, finished units with their check result, pivots and reverts with the trigger, blockers, fixed gates. Skip the trivial.
- A wrong call gets a new row that supersedes it. Never edit or delete history. A new run starts with a `start` row.
- Cells stay single-line; prefix a cell starting with `=`, `+`, `-` or `@` with a quote.
- Before handing back, check each row maps to a real action and its evidence resolves. Add a row for any unlogged fork.
- End the reply with the verdicts, the log path, what is verified and what is open.
- Before you hand back a logged run, a reviewer on another model family reads the log and the transcript. It flags weak evidence, claimed but unrun checks and risky calls. The final message ends with those flags and the reviewer's model.
- A verification or measurement unit's brief names the exact SHAs and the method. A result that does not record them is respawned once, then reported as a gap, never a pass. For a race, declare first-pass, rank-all or best-of before starting.
