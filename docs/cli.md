# Portable CLI

The maintained command guide and the task/review schemas live in the package [CLI reference](../plugins/orchestra/skills/orchestra/references/cli.md). The package carries that guide after installation. This page lists every command.

Run `python3 plugins/orchestra/scripts/orchestra.py [--repo REPO] [--state STATE] [--actor ACTOR] [--lease LEASE] COMMAND`. Each command prints a JSON receipt. A card-moving command adds a `board` key, one line saying what moved and what waits. Run from a linked worktree, any command except `where` is refused when the main checkout holds the run state. `--actor` and `--lease` are consistency checks, not authentication. The Lease column says whether the command needs `--lease` from `start`.

| Command | Purpose | Lease |
| --- | --- | --- |
| `start [--policy FILE] [--harness-session ID] [--new-run] --size tiny\|medium\|large [--asks N] [--owner-request] [--recover [--take-over]]` | Start a run and print the lease once. `--size` is required for a new run; `large` needs `--owner-request`. `--items` is refused (2.4 flag). With `--harness-session`, ending that Claude Code session releases the run. `--new-run` is refused while a stopped autonomous run keeps its report and the owner has no receipt for it. `--recover` (needs `--harness-session`) gives the session that owns the run a fresh lease; `--take-over` with it moves an ended or interrupted run owned by another session to this one, logs it in `progress.md` and arms nothing. An unknown policy key in `--policy` is refused. | no |
| `where` | Print the repository, the state directory and whether `standing-orders.md` exists. | no |
| `status [--brief] [--full]` | Print cards, session state (`size`, `asks`, `owner_request`, or the 2.4 route) and `required_lenses`. `--brief` prints counts, running and reported cards, lease state, autonomy and versions in under 4096 bytes; `--full` keeps the per-file entries of review receipts. Never prints a lease. | no |
| `prepr` | Print the size check and the pre-PR reviewer: `base`, `changed_lines`, `size`, `asks`, `budget`, `over_budget`, `reviewer`, `agent`, `lenses`, `warning`. Read-only; the warning never blocks. | no |
| `board` | Group card ids by role and state; `leftover_worktrees` counts every entry under `.claude/worktrees/`, landed or not. | no |
| `waves` | Print overlaps, unmet prerequisites, ordered waves, the cards startable now, `wave_now` (the cards that start together now), `serialized` (cards held back, each with the card it waits for and why), `idle_workers` and `prep` (blocked builder cards no `prep_for` card prepares). Read-only. | no |
| `worktrees` | List the entries under `.claude/worktrees/` with branch, card, `landed` and `clean`, and print `git worktree remove <path>` for each landed clean one. Read-only; the engine never creates or removes a worktree. | no |
| `refusals [--last N]` | Print the newest refused commands (exit 2) from the refusal log, default 10. Read-only. | no |
| `card TASK [--out FILE]` | Print the brief skeleton rendered for a card, or write it to FILE. Read-only. | no |
| `ledger [--cards ID[,ID]]` | Print BUILD-LEDGER rows (card, role, commit, evidence, status) for accepted cards from engine facts. Read-only. | no |
| `package TASK` | Write a reviewer package (brief, report, self-review, diff stat) under `<state>/packages` and print its path. | no |
| `wave [--inline ID] [--helper REASON] [--serial REASON] [--emit] ID ...` | Start every named card in one step, all or none. `--emit` also prints per card `agent_type`, `model_override`, `isolation`, `fast_forward`, `prompt` (with an `Assignment: WORKER TOKEN` line) and `agent_call`; a card may carry `variant` (`standards` or `medium`). `wave --emit` records each card's base for the `report` base check. | yes |
| `artifact [--tasks ID[,ID]]` | Print the whole-repo artifact, or with `--tasks` the artifact scoped to those cards' reserved files plus HEAD. | no |
| `report [--accept --lease LEASE] WORKER TOKEN FILE` | Record a worker's result file against its assignment token. The same worker may replace the report until the card is accepted or a review covers it. A builder report must answer every acceptance line verbatim. It is refused when its commit is not built on the card's recorded base (recorded by `wave --emit`, or when `dispatch` or `inline` starts the card and none is set). `--accept` (inline cards only) records the report and accepts the card in one call. | no (`--accept`: yes) |
| `autonomy arm\|disarm\|status` | Arm, disarm or inspect the autonomous loop. | no |
| `brief` | Print the newest run brief. Read-only. | no |
| `finding list [--for-brief]` | List the findings ledger, or render a "Known findings" block for reviewer briefs. | no |
| `classify "SHELL COMMAND"` | Print the classifier's decision for a command string without running it. The hook then applies the run state: a `releasemulti` category is the release-multi class, so its result depends on whether a run or autonomy is active. It prints the strict (protect) verdict, including `soften` (`warn` or `allow`) when `normal` mode relaxes it, and `workflow` for a `gh workflow run`. | no |
| `ready` | List cards that can be dispatched now. | yes |
| `route --size TIER [--asks N] --reason TEXT` | Change the tier after `start`, either way; the reason is logged in `route_log`. A 2.4 run uses `route --items N --reason TEXT` instead. | yes |
| `add TASK.json` | Add a card. A builder card may carry `size` (`tiny` or `medium`). On a size run a designer-planner plan card needs a large run or an owner request. On a 2.4 workflow route, the plan card must be accepted first. | yes |
| `dispatch TASK WORKER [--helper REASON]` | Reserve a card for a worker. A tiny builder card (and any builder card on a 2.4 inline route) needs `--helper REASON`. | yes |
| `inline TASK [--report FILE [--accept]] [--serial REASON]` | Reserve a card for the main coordinator. `--report FILE` also records that result file as the report in the same step; a refused report reserves nothing. `--accept` with it also accepts the card. `--serial REASON` starts the card alone although others could start beside it; the reason is logged. | yes |
| `do "STEP" "STEP" ...` | Run several coordinator commands in one call. Each step is one quoted command line without the `orchestra.py` prefix. It stops at the first refusal. A step takes no global option, and cannot be `do`, `start`, `autonomy`, `permit` or `release`. | yes |
| `criterion TASK "CRITERION" --evidence TEXT` | Record your evidence (at most 1000 characters) on an unmet criterion of a reported worker card, so `accept` can pass. `CRITERION` is the text as the report repeats it. | yes |
| `own add TASK PATH` | Add one owned path to a running or reported builder card. `accept` refuses a report that changed files outside the card and names them. | yes |
| `review REVIEW.json [--token TOKEN] [--defer-out-of-scope REASON]` | Record the independent pre-PR review (`final: true`) or the fix re-review (`repair_check: true`). `--token` reports the review card, records the receipt and accepts the card in one step; it covers sibling final lens cards that review the same cards, and takes critic and repair_check receipts. `--defer-out-of-scope REASON` (with `--token`) records each out-of-scope item as deferred to a brief. An empty `cleared` means none; a mismatch refusal names each key with both values; a one-task receipt gets `task_findings` filled; out-of-scope items on a non-final receipt are kept as notes. | yes |
| `accept TASK [--ruling TEXT]` | Accept a card whose current evidence allows it. The refusal names the failing check. `--ruling TEXT` accepts a worker card whose only gap is an unmet criterion, with the coordinator's reason; it is never allowed for an inline card or a failing check. The result carries `warning` when card files have changes not yet committed. | yes |
| `gate [--again] [--timeout SECONDS] NAME -- COMMAND...` | Run a configured check; record the actual exit and log hashes. A passed gate on an unchanged artifact refuses a repeat unless `--again`. `--timeout` overrides `gate_timeout_seconds` for this run. Processes the check leaves running in its own process group are stopped when it exits; one that starts a new session or group is not tracked. | yes |
| `scan` | Run the configured secret scan; an unavailable optional scanner is reported, not passed. | yes |
| `permit REMOTE TARGET` | Create a release permit for an exact remote and target. It stays valid until the artifact changes or the session ends, and is not used up by a release. Refused while autonomy is active. | yes |
| `release REMOTE TARGET` | Run the release command named in policy under a current permit. Refused while autonomy is active. | yes |
| `finding add --review ID --kind finding\|out_of_scope --index N --disposition D --reason TEXT [--card ID]` | Record what happened to a review finding. `ID` may be a unique prefix of 8 or more characters. | yes |
| `hold TASK --finding TEXT` | End the repair ladder: move a blocked repair chain to `held` and log the finding. | yes |
| `pr URL [--task ID]` | Record a pull request the run opened (an http(s) URL). With `gh`, it must be open, from this repository, based on the default or a run branch and headed by the local branch tip; it stores the head, the cards it carries and whether the head has a clean review. A rerun refreshes the entry. The run brief lists it under Needs you. | yes |
| `base TASK` | Print the branch the card's pull request targets: the default branch, or the head branch of its one open parent pull request. Two or more open parents exit 2 with `deferred: wait for pull request(s) N, M to merge`. Read-only. | no |
| `park TASK --reason TEXT` | Set a card aside at an approval boundary. | yes |
| `unpark TASK` | Return a parked card to the queue. | yes |
| `replace OLD TASKFILE` | Add the card in TASKFILE in place of OLD, a queued, reported or parked card: dependencies and review targets move to the new card and OLD is cancelled ("replaced by NEW"), in one write. A refused new card changes nothing. A running or accepted card, a card a review covers and a card in a repair chain are refused. | yes |
| `resume ID` | Send a reported card back to its worker: it runs again under the same token, its report stays as history and the next report replaces it. Refused when a review covers the report (route a repair card) or the worker cap is full. | yes |
| `cancel TASK --reason TEXT` | Drop a queued or parked card that should never run. Refused while another card depends on it, a review covers it or it is in a repair chain; the drop is kept in the state's `cancelled` list. | yes |
| `interrupt` | Stop dispatch and continuation; late reports then fail. | yes |
| `finish [--accept-reported]` | Close the run after completion checks. A parked card blocks it. `--accept-reported` first accepts every reported card whose `accept` passes; the rest stay reported. A refusal for leftover worktrees points to `worktrees`. A run that changed files needs a current final review even with no cards. | yes |

## Changes in 2.15.3

- A result carries a `track` line when the track changed since the last result, so the next step shows right after `add`, `accept` or `wave`.
- `resume ID` is the fix a stale-report refusal names. A resumed card's outside-files check skips commits other cards made while it was reported, so `own add` is no longer needed for them.
- Two repairs collide only on their own files; a non-repair card still waits for a whole running chain.
- A pull request is marked reviewed only from a clean final review, or one that covers every card the pull request carries.
- The `board --view` output has `overlaps`, the card pairs that share files (the same pairs `waves` reports).
- A read-only investigator's report stays acceptable after later edits to the checkout; a builder's report still goes stale.
- `--size` choices are `tiny`, `medium` and `large`, read from the engine.
- A newline before a parenthesis in an acceptance line is no trailing-note gap.
- The engine runs `gh` through the approval module's runner (6 s timeout).

## Changes in 2.15.2

- Model fit ranks families: opus, then sonnet, then haiku. A session at or above a card's family runs the card inline; on the same family the effort decides; a weaker session sends the card to a worker. Policy `model_fit` is `stronger` (the default) or `exact`, which keeps the 2.15.1 rule (any other family goes to a worker). An unknown session model refuses nothing. Track step 1 names only a card `inline` accepts now; while an inline card runs it carries `busy: ID` (shown as `you are running ID`); with none it is `coordinator` with `wait: true`.
- `replace OLD TASKFILE` and `resume ID` are new (rows above). `do` accepts both as steps.
- `accept ID --ruling TEXT` also covers a failing plain check when the ruling names its whole command or a test target of it (a word of six or more characters with `/`, `.`, `:` or `_`). Every failing check must be named; a red-first check is never covered; an inline card takes no ruling.
- A review's out-of-scope item may be recorded `deferred` with a reason (`finding add --kind out_of_scope --disposition deferred --reason TEXT`). The receipt `review` prints lists the out-of-scope items no finding triages yet as `needs_triage`; it refuses nothing.
- Policy `full_check` is `{"paths": [globs], "command": text}`, both nonempty (a malformed value is refused at `start`). When a card's diff (base to reported commit, else its owned files) touches a path, `accept` refuses it unless its self-review lists a passing run of the exact command.
- A red-first check's trailing note is dropped only after a word, so `cd d && (make test)` keeps its subshell. The acceptance check reads each markdown code span on its own.
- Hooks: a resumed worker's second final message replaces the report of a reported card. The restart note names a gate log with no receipt and a recent write, and worktrees with a live process. Under autonomy `rm` below `claude-<uid>` is limited to one session's directory ([hook policy](hooks.md#autonomy-boundaries)).

## Changes in 2.15.1

- `do "report W T F" "accept ID"` reports a worker card and accepts it in one call. `report --accept` stays limited to inline cards.
- `waves` adds `track`: the order the main session works the queue, as steps `{step, card, side}`. A step has `coordinator` and no card when no ready card fits the session model. `serialized` also names a slot or cap (`one inline slot`, `worker cap`, `worktree cap`) as the reason. `wave` prints neither `wave_now` nor `serialized`.
- Model fit covers every role in a sized run, not only builders. Escalation appends the original reason, as `needs-owner:escalated (ORIGINAL REASON)`, only when the card was parked without the `needs-owner:` prefix; any other unfinished card is parked as plain `needs-owner:escalated`.
- `start` and `start --recover` rewrite `NOW.md`. `start` refuses a run owned by another harness session and names `start --recover --take-over`.
- `review --token TOKEN` takes no report path: it reads the report the Stop hook captured. A reported review card is re-taken at the review's artifact so the chain accept can follow.
- `add` refuses a final review brief without a `Lens:` line (and without `Required categories:` for a combined lens), a final review card whose input brief names a `Lens:` its `variant` does not give (the refusal names the variant to set, or says to pass the brief as the card's `brief`), and an acceptance line with `unittest discover -s/-p` that matches no test file. An owned generator source also owns the file the script derives from it. `dispatch` records the card's base.
- `finish` refuses leftover worktrees and points to `worktrees`. A final review stays current after a squash merge when the trees are equal. Untracked `.claude/worktrees/` entries are not evidence.
- A red-first check ignores one trailing parenthetical note. A queued repair holds only its own files against another repair, and its chain's files against any other card. A fix re-review may cover a cleanup card beside the repairs.
- `gate` keeps the output of a killed command. `pr` accepts a stacked base: the head branch of an open pull request the previous run recorded.
- `do -h` is refused as a step. A worker brief points to `orchestra.py card ID` while autonomy is armed.

## Changes in 2.15.0

- New commands: `do`, `criterion` and `own add`. New flags: `status --brief`, `finish --accept-reported`, `inline --report FILE [--accept]` and `start --recover --take-over`. `waves` adds `wave_now` and `serialized`.
- `report --accept`, `inline TASK --report FILE --accept` and a clean fix re-review recorded with `review --token` close cards in fewer calls.
- `accept` refuses a report that changed files outside the card. A file a sibling card owns counts as that sibling's work only when the sibling's own commits made every change to it.
- A card with `"finalize": true` starts only after every other card is accepted, held or parked.
- Refusals name the blocking card, the owning session or the next command.
- The engine rewrites `NOW.md` in the state directory when a lease command runs or a wave is emitted.
- Under autonomy, `do` refuses `autonomy`, `permit` and `release` steps, and the Stop hook nudges a silent worker, then parks the unfinished cards `needs-owner:escalated` on the third unchanged pass (two nudges, then the park).

## Changes in 2.14.0

- New commands: `card`, `ledger`, `package`, `refusals [--last N]` and `worktrees`; new flags `wave --emit`, `report --accept`, `accept --ruling TEXT` and `review --defer-out-of-scope REASON`. The `board` key rides on card-moving command output. There is no `--lease @session` and no engine-owned worktree or `engine_worktrees` policy key: the engine only reads and reports worktrees.
- `start` returns `resume` per requeued card: the old worker and the saved report path.
- The autonomy ledger may carry `- Repairs: up to N per chain` (N from 1 to 3; absent means 1). A sibling repair with disjoint files no longer waits on a parent reservation.
- A worker's shell command carrying `orchestra.py ... --lease` is denied in every guard mode ([hooks](hooks.md#worker-limits-added-in-214)).
- Loosened: out-of-scope items on a non-final review receipt are kept as notes instead of refused.

## Changes in 2.11.0

- New: `base TASK`, `pr URL --task ID`, the policy keys `guard_mode` (`normal` or `protect`), `release_workflows` and `max_worktrees` (default 3), and the `UserPromptSubmit` approval hook. An unknown policy key is refused at `start`.
- Changed: `complete` waits for a verified pull request when the branch holds commits; every stop of an autonomous run keeps its report; the ledger's Merge, Push and Deletion lines changed, and a pre-2.11 ledger is refused at `arm` with a re-fill message; `arm` moves an earlier approval receipt aside.
- Run engine commands from the main checkout. A linked worktree resolves a different state directory, so the run is not found there.

## Changes in 2.7.1

- `start --recover --harness-session ID` gives the session that owns the run a fresh lease when it has lost its own (after compaction or a restart). Running cards keep their assignments; release permits are cleared. The id is in the SessionStart context.
- `cancel TASK --reason TEXT` drops a card that should never run.
- A worker that cannot do its card ends its report with a line `BLOCKED: reason`. The card is parked with that reason; no `SELF_REVIEW` is needed.
- The files already modified or untracked when a run starts are recorded as its baseline: the size warning and the review lenses count only what the run changes. Interpreter leftovers (`__pycache__`, `*.pyc`, tool caches, `.DS_Store`) are never evidence.
- Evidence stays strict: staging or committing after a review makes it stale. After committing, record the independent review again, then `accept` succeeds (the report needs unchanged files, not the same HEAD). Sparse-checkout paths and deletions are handled; interpreter leftovers are never evidence.
- `review` names the keys a report file is missing.
- `autonomy arm` records a digest of each remote's push URL, not the URL.

## Changes in 2.6.0

- Removed: the relaunch harness, `orchestra.py relaunch`, `autonomy arm --relaunch` and `autonomy settle`. A 2.5 state armed with `--relaunch` does not re-arm on `start`; re-arm in a live session.
- Changed: during an interactive run, a release action without a current permit asks the user instead of being denied.
- Changed: under autonomy the pull request push has one exact shape, and merged branches and worktrees may be cleaned up ([hook policy](hooks.md#autonomy-boundaries)).
- Changed: the Stop loop continues a turn only on actionable work: a ready or reported card, an open final finding, or a held chain owed its final review.
- Changed: `start --policy` validates the policy file, and CLI errors exit 2 with a JSON error.

## Changes in 2.0.0

- Removed: the three advisory commands for lane routing, review grouping and audit-axis selection. The coordinator now chooses lanes, groups reported cards and picks audit axes by hand, following the skill's coordination and audit-axes references. Calling a removed command exits with an unknown-command error.
- New: `artifact --tasks`, `autonomy arm|disarm|status`, `park`, `unpark` and `where`; `start --harness-session`.
- `status` and `board` no longer show the lease. `start` still prints it once. If it is lost, end the harness session (SessionEnd releases the run). For a run without a harness session, read the actor and lease from the run's `state.json` in the state directory and run `interrupt` with them. The lease is a consistency token, not a secret.
- The policy keys `reserved_ports` and `denied_tools` are gone. An old policy file that still carries them loads unchanged.
- `required_review_categories` may be narrowed to a non-empty subset of the seven final-review categories.
- A live run is invalidated only when a role or a mode is added, removed or renamed. Editing a skill or method file no longer invalidates it.

## Changes in 2.2.0

- New: `hold`, `brief`, `finding add|list`, `gate --again`, `autonomy arm --relaunch`, `autonomy settle` and `relaunch`. The 2.2 wave field and `supersede` are removed in 2.4; the relaunch harness, `--relaunch` and `settle` are removed in 2.6.
- Changed: autonomy has no pass or stall cap. Caps in a 2.1 ledger are recorded, not enforced. The run brief replaces the autonomy report.
- Changed: `gate` refuses boundary commands, and a repeat of a passed gate needs `--again`.
- Every 2.1 command keeps working. A run started under 2.1 loads under 2.2; see the README upgrade note before mixing versions on one run.

## Changes in 2.5.0

- New: `start --size`, `--asks`, `--owner-request`, `route --size`, `prepr`, the builder card `size` field, and the reviewer agent `code-reviewer-medium` (`Lens: combined`).
- Changed: a new run needs `--size`; `start --items` is refused. A 2.4 run keeps `route --items` and its item routes.
- New: `gate --timeout SECONDS` for one run. `report` replaces a reported card's report for the same worker and token until the card is accepted, a review lists it or a repair of it exists ("A review covers this report; route a change through a repair card").
- Changed: a builder report needs a nonempty `ARTIFACT:` line ("Builder report needs a nonempty ARTIFACT line").

## Changes in 2.4.0

- New: `start --items N`, `route`, `dispatch --helper REASON`, the `SELF_REVIEW:` builder line, `required_lenses` in `status`, and the policy keys `sensitive_paths` and `standards_min_lines` (default 200). Lenses: correctness always; security when a changed file matches `sensitive_paths`; standards and cleanup above `standards_min_lines` changed lines.
- Changed: only the pre-PR review and the fix re-review are recorded. Reviewers cite gate receipts (`current_gate_ids`) and do not rerun suites.
- Removed: waves, `supersede`, `task_findings`, the checkpoint review and the checkpoint reviewer.

## Scoped evidence

A task report binds to the covered cards' reserved files, the index, the status and the policy, not to HEAD. An uncommitted edit outside those files does not stale the evidence, and a commit that leaves those files alone does not either; an edit inside them does. `accept` compares the reported commit. A card with no reserved files gets the whole-repo artifact. Reviews, gates, release permits, release receipts and completion evidence always bind to the whole repository. The newest receipt per category that covers a card decides that category. If it is stale there is no current verdict; the engine never falls back to an older receipt.

## Repair and hold

The repair ladder has one repair rung: the Sonnet implementation card, then one Opus builder `repair` card, then one fix re-review (`repair_check: true`, `final: false`). `hold TASK --finding TEXT` ends it. It is refused unless TASK is a repair card in state `reported` with a current blocking verdict, or an implementation card whose current blocking verdict comes from a fix re-review. It moves the whole chain to `held`, stores the finding and appends a `held` line to `<state>/progress.md`. A held card reserves nothing and satisfies a dependency; `finish` still needs the final phase to clear it.

Accept a card before adding a repair that overlaps its evidence: dispatching a repair is refused while a reported card passes every `accept` check and shares reserved files with it ("Accept X first; a repair would make its evidence stale").

## Findings ledger and run brief

`finding add` records a disposition for one item of a recorded review: `--kind finding` takes `rejected`, `deferred`, `inline`, `card` or `brief`; `--kind out_of_scope` takes `inline`, `card`, `brief` or `deferred`. `--index` points at the item in that receipt, and `--card` names the card for `card`. A rejection never accepts a card: acceptance still needs a fresh independent verdict, which the repair-diff check gives. `finding list` prints every entry; `finding list --for-brief` prints a "Known findings" block (id, disposition, text, reason) to paste into a reviewer brief.

Every end of a run, armed or not, appends a run brief to `<state>/progress.md` and stores it as `last_brief`. `brief` prints it without a lease and changes nothing. Sections, in order: reason, deadline, passes and stalls; Needs you; Still failing / next phase; Held log; Final rounds; Notes; Deferred findings; Parked, Accepted and Failures. SessionStart shows its first 2000 characters. Every write to `progress.md` is a single append.

`gate --again` reruns a check that already passed on the same artifact with the same argv. A failed gate always reruns. A gate refuses every command the guard does not classify `allow`, and every boundary command (deletion, merge, branch deletion): those run only through the guarded hook.

## Autonomy

`autonomy arm` needs an active run. If `<state>/autonomy.md` does not exist, `arm` writes the ledger from a template, prints its path and refuses; fill it in and arm again. The ledger holds a goal, completion checks, a deadline and the fixed approval boundaries. `max_passes` and `max_stalls` are optional: a ledger that still carries them (as 2.1 ledgers do) records and shows them, and never enforces them. Any change to the ledger after `arm` stops the loop. While armed, the Stop hook keeps the run going until the deadline, completion, only parked cards that all need the owner (`parked-only`), a tampered ledger, the third unchanged nudge (`needs-owner:escalated`) or `disarm`. With nothing live, an idle board, a failing gate, an unchanged pass, a silent worker or an unpublished branch each gets a nudge; the same unchanged board three times parks every unfinished card `needs-owner:escalated` and stops the run. It continues a turn only when the coordinator can act now: a ready or reported card, an open final finding, a held chain owed its final review, or, with every card accepted, the final review, gates and pull request still owed. When only workers are running, the turn ends and the harness wakes the session as each one finishes. A continuation is never sent twice for the same progress signature: a continued turn that changes nothing ends and counts as a stall. No count of passes or stalls stops the run; the band shows "pass N". Ending the session ends autonomy when the run was started with `--harness-session`; arm only such a run. Each stop writes a run brief to `<state>/progress.md`, shown at the next session start.

The ledger holds exactly one `- Release:` line: `- Release: no release, permit or deploy.` by default, or `- Release: pre-authorized <remote> <target>`, which must equal `policy.release` (enabled, same remote and target) or `arm` refuses. The pre-authorization lets `permit` and `release` through for that exact remote and target only, and overrides the Push and Engine-gated actions lines for them. Autonomy may push its own branches, open, review and stack pull requests with `gh`, and clean up what it created; it never merges to the default branch. The owner types `approved`, and the merges run in the printed order ([approval flow](hooks.md#approval-and-the-merge-guard)). A push must be exactly `git push [-u|--set-upstream] <remote> <refspec>` with a configured remote name, a local branch as source and one destination branch other than the remote's default branch, `main` or `master` ([hook policy](hooks.md#autonomy-boundaries)). Cleanup covers the run's own branches and worktrees, provably merged branches and files inside a linked worktree. A ledger with the 2.5 line `- Push: no push to any branch.` is refused at `arm`. Everything else stays denied while autonomy is active: every other push and permit, release inside a multi-command line, other deletion, and local merges on the default branch. The coordinator parks the card and continues with others. `arm` reports the permission mode and a keep-awake reminder and changes neither. Credential entry is a prose rule only and is not detected.

