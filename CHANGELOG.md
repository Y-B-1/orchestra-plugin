# Changelog

Release 2.0.0 is described in docs/RELEASE-NOTES-2.0.0.md.

## 2.15.3 — 2026-10-27

Closes the friction and review notes left from 2.15.2 and 2.15.1 (F112 to F121, N1 to N5, N8, N9, F39).

- **Resume and repair:** a resumed card's outside-files check skips commits other cards made while it was reported, so `accept` no longer asks for `own add` (F112). Two repairs collide only on their own files, not on the files of their whole chains, so repairs with disjoint files run side by side (F114).
- **Pull requests:** a pull request counts as reviewed only from a clean final review, or from one that covers every card the pull request carries (N4). A narrow scoped review no longer marks it reviewed.
- **Clearer results:** a CLI result carries a `track` line when the track changed since the last result, so the coordinator sees the next step right after `add`, `accept` or `wave`. This replaces the 2.15.2 gap about the first prompt after a CLI `add`. `own add` on a reported card keeps its report current after the card's commit was merged into this checkout; a file edited after the reported commit still leaves it stale. A stale-report refusal names `resume ID` as the fix (F117). A sibling commit merged in from its own branch stays that sibling's work after this card takes over one of its files; this card's own commit that touches a sibling's file still counts as outside (F121). `--size` choices come from the engine's size list. A newline before a parenthesis in an acceptance line is no trailing-note gap.
- **Board:** the board view has `overlaps`, and the mod's Track lane draws "Shares files: a and c" (F39). A pending board note that the board has moved past prints the current board line instead (F118).
- **Hooks:** a read-only investigator's report stays acceptable after later edits to the checkout (F116). The Stop hook stays quiet while a gate log has no receipt yet, instead of asking to accept a card that waits on it (F115). The approval prompt hook shares one deadline across its lock wait and `gh` calls, under the 10 s hook timeout (N2).
- **Merge guard:** under an active run, `gh repo set-default` is denied, because it changes which repository a later merge targets (N1). A lower pull request closed without merging makes the guard say "type approved again" (N3). A gated merge with no method flag is denied (N5), and the no-method deny says "add --merge", the one method flag a gated merge accepts (F119). The engine runs `gh` through the approval module's runner with its 6 s timeout (was 10 s) (N8).
- **Test-suite classifier:** it reads `coverage run`, short option clusters such as `-Bm` and script arguments (`script.py -m pytest` is the script's option, not a suite run).
- **Live checks:** new `scripts/live-gh-wizard.sh` and `docs/live-gh.md`: the owner's one-time check of the merge guard against real `gh` on a throwaway repository (L2). New live scenario `l3` (23 scenarios): background output and a subagent answer that say "approved" reach no approval (7/7 live pass). `t3` says whether the mod loaded when it skips.
- **Docs:** mods run by default from Claude Code 2.1.287, and the docs name `--bare`, `--safe-mode` and `disableAllHooks` as the off switches (N9: the README states the live-check evidence). `gate.md` says the full suite runs only on the owner's explicit request.
- **Tests:** `report` inside `do` (F89) and the `binds` edge case are pinned. Stale checkpoint test names are renamed and two `review_of` tests use a real mode. The merged-delete hook tests use a temporary state home, so a test run no longer leaves policy-only folders in the state directory.

### Known gaps

- `t3` still skips headless: the board mod's task calls do not appear under `claude -p`, so native task renumbering is proven by mod unit tests only. The skip note now says `mod loaded` or `mod not loaded`.
- L2 needs the owner to run `scripts/live-gh-wizard.sh` once.
- Windows and the GitHub branch ruleset are untested.

## 2.15.2 — 2026-10-27

The main session runs the main track, and the friction left from 2.15.1 (F97 to F107).

- **Model fit ranks families:** a session at or above a card's model family (opus, then sonnet, then haiku) runs the card inline; on the same family the effort decides. A weaker session sends the card to a worker. The policy key `model_fit` is `stronger` (the default) or `exact`, which keeps the 2.15.1 rule (any other family goes to a worker). Track step 1 names only a card that `inline` accepts now; with none it says `wait: true`. The shared model constants live in `orchestra_core/models.py`, so the engine no longer imports the hooks.
- **Native tasks follow the track:** the mod renumbers a task subject's `step N` when the track changes and drops it when the card leaves the track.
- **`replace OLD TASKFILE`:** adds a card in place of a queued, reported or parked one. Dependencies and review targets move to the new card and the old one is cancelled, in one write; a refused new card changes nothing. A running or accepted card, a card a review covers and a card in a repair chain are refused.
- **`resume ID`:** sends a reported card back to its worker, running again under the same token. Its report stays as history and the worker's next report replaces it. A report a review covers is refused.
- **Rulings on failing checks:** `accept ID --ruling TEXT` also covers a failing plain check when the ruling names its command or its test target. Every failing check must be named; a red-first check is never rulable; an inline card takes no ruling.
- **Out-of-scope notes:** a review's out-of-scope item may be triaged `deferred` with a reason. A final review receipt lists the items nobody triaged yet as `needs_triage`, and refuses nothing.
- **Policy `full_check`:** `{"paths": [globs], "command": text}`. A card whose diff touches one of the paths needs a passing run of the command in its self-review, or `accept` refuses it.
- **Checks:** a red-first check's trailing note is dropped only after a word, so `cd d && (make test)` keeps its subshell (F70). The acceptance check reads each markdown code span on its own (F105).
- **Guard (denies stay as they were except where noted):** under autonomy `rm` below `claude-<uid>` may remove only paths inside one session's directory (the current session's when its id is known); `rm -rf` of the `claude-<uid>` directory itself and a project-level glob below it are denied. A glob directly under the temp directory with a prefix that cannot start `claude-` or `cc-` (`foo*.log`) is allowed again; `/tmp/*`, `/tmp/cl*` and `/tmp/cc*` are denied, and so is any operand naming a `cc-` entry (Claude Code's sockets). A `$TMPDIR` operand is refused with a note to write the path in full, since the shell may export another TMPDIR than the hook, and a `$TMPDIR` under `/tmp` or with a `claude-` part adds no temp root. `cd DIR && git worktree remove` judges the own-worktree check against the session's directory. `__pycache__/` and `*.pyc` do not block cleanup; any other ignored file still does.
- **Hooks:** `PostModelSwitch` passes the session id, so another bound session cannot rewrite the run's model. The prompt's Model fit line uses the engine rule. After a report, only `resume` lets the worker's next final message replace the report (F102); without it the message is ignored. The restart note lists a gate log with no receipt and a recent write (F103) and worktrees with a live process (F106).
- **Live matrix:** 22 scenarios. `t1` runs the main track in a real Opus session: the board said `Track: you run A; side: C`, the session wrote `a.txt` itself, a worker ran C before A was accepted, and the track then named B. `a4` proves the scratchpad delete rule on a decoy Claude temp tree.
- **Clearer next steps:** a refused ruling says to name the failing command or its test target (F108). A reported code review card is not offered for `accept`: `Next:` and its native task name `review --token` (F109). `add` warns when a running final review will not cover the new card (F110). `finding add --review` takes a unique prefix of 8 or more characters of a receipt id (F113).
- **Main session keeps moving:** a reported inline card no longer reserves the main session, so it starts the next inline card while the first waits for acceptance (F111). `resume` restarts the card's silence clock. `replace` waits while a running review reads the old card.
- **Review fixes:** the acceptance check reads each markdown code span and then the prose outside the spans. A ruling names a check only by a whole word that no option follows, never by a `cd` operand. The prompt Model fit line leaves out review and tiny cards. Under autonomy the `claude-<uid>` temp check ignores case (APFS), an ignored file inside a `__pycache__/` folder blocks cleanup, a refused resumed report no longer overwrites the saved one, and a bound run skips a model record with no session id. The mod's Track lane shows the `wait` step. While the main session's inline card runs, track step 1 says `you are running X` instead of blaming the model. The wave checkpoint uses the same inline-slot rule as a start, and `resume` refuses a second running inline card. A ruling followed by a sentence end or ` - ` still names its check; `full_check` counts a check with a trailing note; `replace` passes on the running-review warning. The Model fit line says `a stronger model or a higher effort`.
- **Tests:** `test_patch_equivalent_work_counts_as_landed` no longer depends on the clock second (F107). The crafted-shell reading budget is measured in CPU time, so machine load cannot fail it.
- **Docs:** `docs/cli.md` and the CLI reference describe the commands and keys above; the 2.15.1 notes are corrected (below).

### Corrections to 2.15.1 wording

- `rm -rf /tmp/*` under autonomy is denied (2.15.1 and later), not allowed as the 2.15.1 ledger said.
- Escalation adds the original reason only when the card was already parked without the `needs-owner:` prefix. A queued, running or reported card is parked plain `needs-owner:escalated`, and a card already parked `needs-owner:` keeps its text.
- `cancelBoardTimer` in `orchestra.ts` is used (twice), so the 2.15.1 note that it is unused was wrong.
- The command is `start`, not the internal `open_session`.

### Known gaps

- `t3` records a skip in headless runs, because the board mod does not run under `claude -p`; native task renumbering is proven by the mod unit tests only.
- The first prompt after cards are added by CLI shows no board line (the CLI marks the board seen), and the session model reads unknown until the first `orchestra.py` call.
- A resumed inline card can need `own add` for files of another card that landed while it was reported (F112).
- A repair reserves every file of its chain, so two repairs whose chains share a file run one after the other (F114).

## 2.15.1 — 2026-10-26

Friction from the 2.15 live run, and the review notes 2.15.0 deferred.

- **Model fit for every role:** in a sized run the engine checks the session model for investigator, designer-planner and every other worker card, not only builders. The rule is stated once in the coordinator skill.
- **`waves` returns `track`:** the order the main session works the queue, as steps `{step, card, side}`; a step has `coordinator` and no card when no ready card fits the session model. `serialized` also names a slot or cap as its reason (`one inline slot`, `worker cap`, `worktree cap`). Only `waves` prints `wave_now` and `serialized`; `wave` does not, and the CLI reference now says so. The board line ends `Track: you run E2; side: H, M`, the Kanban pane orders cards by step, and the native task list gets an `accept-ID` entry per reported card.
- **Escalation keeps the reason:** a parked card becomes `needs-owner:escalated (ORIGINAL REASON)`, so the reason the owner reads is not lost.
- **Take-over:** a plain `start` refuses a run owned by another harness session and names `start --recover --take-over`. `start` and `start --recover` rewrite `NOW.md`. A SessionStart, Stop or PreToolUse from a session the run is not bound to no longer rewrites the recorded model.
- **Review:** `review --token TOKEN` takes no report path and reads the captured report. A final review stays current after a squash merge when the trees are equal. A reported review card is re-taken at the review's artifact so the chain accept follows. A fix re-review may cover a cleanup card beside the repairs.
- **`add` checks:** a final review brief needs a `Lens:` line (and `Required categories:` for a combined lens); an acceptance line with `unittest discover -s/-p` must match a test file; an owned generator source also owns the file its script derives. `dispatch` records the card's base.
- **Repairs and checks:** a queued repair holds only its own files against another repair and its chain's files against any other card. A red-first check ignores one trailing parenthetical note. `gate` keeps the output of a command it killed. A `pr` may be stacked on the head branch of an open pull request the previous run recorded. Merges stay one pull request into the default branch at a time.
- **`finish` and `status`:** `finish` refuses leftover worktrees and points to `worktrees`; an untracked `.claude/worktrees/` entry is not evidence. `do -h` is refused as a step.
- **Guard (denies only get sharper or more precise):** autonomy cleanup removes a worktree only when it is clean (no ignored file), merged and on a branch the run made. An `rm` glob under the temp directory may not empty a `claude-*` scratch directory, and a worktree `rm` refuses a `..` operand or a glob before the last component. A refused `git push` chain says the push shape is the cause. A silent worker is listed as `alive`, `gone` or `liveness unknown`. A prompt that is not the approval word still ends an armed run past its deadline. Worker briefs point to `orchestra.py card ID`, because the state directory is closed to workers while autonomy is armed.
- **Tests:** the F89 timing tests compare a crafted nested shell with a benign twin instead of a fixed 5 s, and the M3 card gave them a 30 s per-test timeout (`timeoutMs`).
- **Code cleanup:** the dead `stalled` and `gate-failing` reason tests are gone from the run-brief builder; `EFFORTS` has one definition; the hooks share one transcript tail reader and one `rm` operand reader.
- **Docs:** the README command table lists every subcommand (checked by `tests/test_readme_commands.py`); `do "report W T F" "accept ID"` is documented as the one-call report and accept for a worker card; the repeated model-fit prose and the fold sentence are gone from the loaded skills.

### Corrections to 2.15.0 wording

- The deny text for a question with no recommended option is `DECIDE_OR_PARK` in `hooks.py`: "Autonomy is armed and the owner is away. Decide this yourself: take the option you would recommend, record the decision in your next message, and continue", then how to park. The 2.15.0 entry quoted shorter wording.
- A park without the `needs-owner:` prefix is not undone by a hook. The Stop nudge tells the coordinator to run `unpark`, and escalation relabels an unprefixed park `needs-owner:escalated (REASON)`.
- The model is recorded at five hook events, not three: SessionStart, Stop, a PreToolUse shell command that names `orchestra.py`, PostModelSwitch and UserPromptSubmit.
- Escalation comes on the third unchanged pass (two nudges, then the park); earlier text counted three nudges.

### Known gaps

- Items deferred to the next release (F97 to F101) are listed in `docs/BUILD-LEDGER.md`.
- The `cancelBoardTimer` wrapper in `orchestra.ts` and the repeated "A tiny task starts no run" prose are left: the first sits outside this card's files, and `tests/test_skill_routing.py` pins the second in two files.

## 2.15.0 — 2026-10-25

Autonomy works like a goal, a card runs where its model fits, and the coordinator needs fewer engine turns.

- **Autonomy keeps going like a goal:** the Stop hook nudges an idle board, a failing gate, an unchanged pass, a silent worker or an unpublished branch instead of stopping. On the third unchanged pass (two nudges, then the park) it parks every unfinished card `needs-owner:escalated` and stops the run. A park without the `needs-owner:` prefix is undone, and both park instructions give the prefix.
- **Autonomy answers its own questions:** while armed, an `AskUserQuestion` whose questions all have a "(Recommended)" option is answered by the hook and logged as `decided for the owner` in `progress.md`. Any other question is denied with "decide it yourself, record the decision, or park the card", and a Stop that ends with a question gets the same text.
- **Autonomy cleanup allowances:** an armed run removes its merged clean worktrees, deletes branches provably merged or made by the run, and deletes files under the system temp directory. Every other deletion stays denied.
- **Model fit replaces folding:** hooks record the session model at SessionStart, PostModelSwitch and UserPromptSubmit, and the prompt adds a `Session model:` line naming queued cards that need a worker. A card on another model family, or a higher effort, starts only on a worker; `inline` refuses it. Critic and reviewer cards always go to workers.
- **The coordinator skill routes by context, model fit and failure kind:** split by context, not by role; the agent that holds a unit's context does all of it. Role skill descriptions say the main session may load them for an inline card.
- **`do`:** `do "STEP" "STEP" ...` runs several coordinator commands in one call and stops at the first refusal.
- **`--accept` closes in one call:** `inline TASK --report FILE --accept` reserves, reports and accepts an inline card in one state write. `inline TASK --report FILE` without `--accept` records the report and leaves the card reported; a refused report reserves nothing.
- **Chain accept:** a CLEAN fix re-review recorded with `review --token` also accepts the repair chain it closes, each card only when `accept` would take it.
- **`finish --accept-reported`:** first accepts every reported card whose `accept` passes; the rest stay reported.
- **`criterion`:** `criterion TASK "CRITERION" --evidence TEXT` records your evidence on an unmet criterion of a reported worker card, so `accept` can pass.
- **`status --brief`:** prints counts, running and reported cards, lease, autonomy and versions in under 4096 bytes, with no lease.
- **`own add TASK PATH`:** adds one owned path to a running or reported builder card. `accept` refuses a report that changed files outside the card and names them.
- **`NOW.md`:** the engine rewrites one short present-state file in the state directory whenever a lease command runs or a wave is emitted. Worker briefs point to it.
- **A tiny task starts no run:** edit, check and commit inline, with no `start`, cards or `finish`.
- **Lease and restart:** after a restart of the same conversation the coordinator keeps its lease. A forked session reads only until `start --recover --take-over`. SessionStart lists dead workers, dirty worktrees, the brief's age and the worker transcripts written in the last 2 minutes.
- **Clearer refusals:** a refused start names the blocking card and the cause, and refusals list valid values and the next command. Lease refusals name the owning session and the fix. `waves` adds `wave_now` (the cards that can start together) and `serialized` (startable cards that must wait).
- **`finalize` card:** a card with `"finalize": true` starts only after every other card is accepted, held or parked.
- **The board pane in the app:** the pane opens by itself when autonomy arms. The header shows the pass, stall, deadline and worker line, and the pane adds "Needs you" and "Decided for you" sections and a toast for each card that parks, reports or is accepted. The native task mirror needs `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` on 5.5 models, and the pane says so.
- **Generator tool checks:** `generate.py` refuses an unknown tool name and an oversized agent catalog. It checks the worker delegate and read-only rules first, so a worker that pins `Agent` or `Task` fails with "workers never delegate".
- **Live matrix:** new scenarios `m1` (model fit) and `s1` (role skills); `--repeat N` runs each scenario N times and names flips; `d4` accepts a builder whose `tools:` line has no `Agent`.
- **Review grants no permission:** the pre-PR review reference says again that a review grants no external permission, with a test that pins it.
- **A silent worker is gone, not live:** on an unchanged board, an armed run no longer counts a running card whose worker is silent as live work. Only live background workers and the inline card count, so the run nudges and then escalates instead of idling.
- **`do` refuses owner steps:** `do` refuses `autonomy`, `permit` and `release` steps. The guard reads each quoted `do` step like a direct call, so an armed run cannot disarm itself through `do`.
- **Temp `rm` globs:** under autonomy, an `rm` below the temp directory may carry a glob only in its last path component. A glob earlier in the path could match a link that leaves the temp directory.
- **Sibling files in `accept`:** a file that a sibling card owns counts as that sibling's work only when the sibling's own commits made every change to it. A change by this card's commit now lists the file as outside the card.
- **Quoted delimiters after `>&N`:** the state-write check now reads `cd STATE && echo x >&1" "/../state.json` (and `' '`, `";"`, `"|"`) as a write. It drops a descriptor copy before a quote only when that quote closes an open string. Second repair of this chain, approved by the owner.

### Known gaps

- The state-write check reads `>&N` followed by a quote with its own quote tracker, which ignores `$'...'` escapes, `#` comments and heredoc bodies: a quote inside one of those can still hide a write such as `echo $'\'' >&1' '/../state.json`. The guard is best effort.
- Review notes deferred to a follow-up are listed in `docs/BUILD-LEDGER.md`.

## 2.14.2 — 2026-10-24

Fixes for the friction the 2.14.1 run hit, and the guard gaps its reviews found.

- **Workflow reports are captured again:** Claude Code now starts a Workflow agent's transcript with a relayed copy of the user's request, so the `Assignment:` line moved to the second user message and `SubagentStop` capture filed every Workflow builder's report as `unmatched-<agent>.md`. Capture now reads every user message in the first 64 lines and uses the first assignment that names a running card (F62).
- **The board names only cards `accept` takes:** `board --view` adds `acceptable_now`, the reported cards that are not under repair, not waiting on a queued or running review, and whose self-review passes. The Stop hook and the prompt board line name `accept` only for those (F60).
- **A second repair needs the owner's words:** a repair of a held chain must carry `owner_approval`, the owner's quoted text; the engine stores it on the card and logs it in `progress.md`. It is refused while autonomy is armed (F61).
- **`finish` after a clean fix re-review:** the fix re-review cards of a closed repair chain now count as covered by the final review they fix, so no extra final review is needed (F63).
- **Clearer refusals:** "review targets not reported" names the `report WORKER TOKEN FILE` fallback, and "Review covers incomplete work" names the unfinished cards (F51, F62).
- **Tolerant receipt fields:** a review `artifact` of `<sha> clean (a note)` and a `gate_receipts` entry with prose around its 32-hex id now record (F58, F64).
- **State-write guard gaps closed:** `>&FILE`, `(cd <state> && ...)`, `{ cd <state>; ...; }`, `pushd`, `builtin cd`, `touch`, `mkdir` and `cp -r` onto a coordinator note are denied (D1, D2).
- **Gate order:** `scripts/check.sh` runs the mod tests before the unit suites start, so their 5 s per-test limit no longer fails under load (F57b). `scripts/live-matrix.py` removes only scenario directories it made.

## 2.14.1 — 2026-10-24

Fixes from the first live test of the installed plugin in real headless Claude Code sessions (`scripts/live-matrix.py`).

- **Worker lease deny under the mod:** with the TypeScript mod running, the Python hook skipped an `orchestra:` worker's `orchestra.py --lease` command, so the 2.14.0 deny never fired live. The mod shortcut now sends that call to Python.
- **Engine state is protected from shell writes in every mode:** a shell redirect, `tee`, `rm`, `mv`, `cp`, `ln`, `truncate`, `dd`, `chmod` or `sed -i` into the run's state directory is denied in `minimal`, `normal` and `protect`. One `echo >> state.json` used to corrupt the run and then lock the session as if autonomy were active. Outside an autonomy or unattended lock, the shell rule allows the coordinator notes the Write rule allows at the state root (`progress.md`, `standing-orders.md`), so `echo >> progress.md` works; `autonomy.md` and the other state files stay denied. The `>|` redirect and the `-t DIR` form of `cp` and `install` are denied too. A `cd` into the state directory keeps writes denied for the rest of the command: every later redirect or write verb with a relative target is denied, whatever `cd` follows. Reads and `orchestra.py` commands stay allowed.
- **`protect` allows the pull-request push:** `git push [-u] REMOTE BRANCH` of a feature branch no longer needs a release permit outside a lock, as under autonomy. The default branch, `main`, `master`, protected branches, the release target, force pushes and URL remotes stay denied; an unresolvable default denies.
- **Live test matrix:** `scripts/live-matrix.py` runs 16 scenarios in real `claude -p` sessions against the installed plugin or, with `--plugin-dir`, a candidate. See docs/live-matrix.md. `scripts/check.sh` never runs it.

## 2.14.0 — 2026-10-24

Built from the audit proposals and the friction log of the 2.13 run: fewer hand steps between a worker's report and an accepted card, and a board the coordinator sees without asking.

- **Widest dispatch (owner request).** An investigator card may carry `prep_for: ID` and start at once while its target is blocked; its accepted report appears in the target's brief under `## Prep notes`. `waves` and `wave` print `idle_workers` and `prep` (blocked builder cards nobody prepares). The coordinator and planner texts say to start every disjoint unit at once and to run read-only prep and lookahead research immediately.

Audit proposals:
- **Worker reports are captured:** a `SubagentStop` hook saves each `orchestra:` agent's final message to `<state>/reports/<token>.md` and records it as the card's report (P1).
- **`accept` compares the reported commit:** scoped evidence binds a card's files, index, status and policy, not HEAD, so a commit that leaves those files alone no longer stales it (P2, F3).
- **`wave --emit` and `card ID`:** the engine prints per card the agent type, model override, isolation, fast-forward flag, prompt with its `Assignment:` line and the `agent_call`, and renders the brief skeleton (P3, F33).
- **`ledger` and `package TASK`:** BUILD-LEDGER rows and a reviewer package written from engine facts (P4).
- **A report answers every acceptance line:** `report` refuses a builder report that leaves an acceptance line unanswered; `accept --ruling TEXT` records the coordinator's ruling on an unmet criterion (never for an inline card); `report --accept` closes an inline card in one call (P5, F20).
- **`refusals [--last N]`:** a log of refused commands with a read command (P6).
- **Refusals name the field:** `accept` names the failing check, and a receipt mismatch names each key with both values (P8, F31, F32).
- **The board as a stone on the path:** a one-line `board` key on card-moving command output; a `PostToolUse` hook on `Agent|Task` delivers a pending change once; `UserPromptSubmit` adds a board line only when the board changed; `Stop` blocks once outside autonomy while a card waits (P9).

Friction fixed:
- **F1 resume:** `start` returns `resume` per requeued card, with the old worker and the saved report path.
- **F7 linked worktree:** the CLI refuses from a linked worktree when the main checkout holds the run state, and leaves no empty state behind; `where` is exempt.
- **Leftover worktrees:** the read-only `worktrees` command lists `.claude/worktrees/` entries with branch, card, landed and clean, and prints the removal commands; `board` shows `leftover_worktrees` and `finish` points to the command. `report` refuses a commit built on the wrong base (a base is recorded by `wave --emit`).
- **F15 repairs per chain:** the autonomy ledger line `- Repairs: up to N per chain` (1 to 3, absent means 1).
- **F30 sibling repair:** a repair with disjoint files no longer waits on a parent reservation.
- **F2, F23, F28, F31 receipts:** an empty `cleared` means none; a one-task receipt gets `task_findings` filled; mismatch refusals name each key with both values. Loosening: out-of-scope items on a non-final receipt are kept as notes instead of refused.
- **F4, F27 `review --token`:** covers sibling final lens cards that review the same cards, takes critic and repair_check receipts, and `--defer-out-of-scope REASON` records out-of-scope items as deferred.
- **WDENY2 worker lease:** a worker's shell command carrying `orchestra.py ... --lease` is denied in every guard mode.
- **F23 spawn without Mode:** the Kanban module refuses an `orchestra:` spawn whose brief has no `Mode:` line (TypeScript module only; the Python hooks have no equal).
- **F34 branch deletion:** the refusal now reads "Run each branch deletion as its own command, not chained or batched with other calls".
- **F12, F24, F25, F26, F28 text:** skill and `scripts/check.sh` text name the rules from the 2.13 run.
- **Normal mode:** softening reads past a trailing shell comment.

Skipped or deferred:
- F35 (`finish` after a fix re-review): not reproducible; finish counts a clean fix re-review.
- F6, F10, F36 (heredoc text read as a command), F22 (malformed quoting) and F24 (old, unittest rerun read as a suite): not reproducible at the base.
- F18 (`pr merge` as a release kind): deferred; it changes release authority.
- F21 (a second inline card): deferred; it weakens the one-inline rule.
- `--lease @session`: dropped after the plan critic's finding 1.
- Engine-owned worktrees and an `engine_worktrees` policy key: deferred for permission and guard risk; the engine only lists worktrees.
- F38, F39, F40, F43 (amend a queued card, a waves overlap view, a sibling-fixture ruling): found during this run and queued.

## 2.13.1 — 2026-10-24

- **`finish` works after a squash merge:** a reported commit also counts as landed when a commit the engine gated or reviewed contains it and `HEAD`'s last 50 first-parent commits hold that commit's tree, or its whole patch from their merge base. 2.13.0 refused every run whose work was squash-merged. Work that never merged is still refused.

## 2.13.0 — 2026-10-24

Parallel waves, a live Kanban board with native task sync, and a guard that leaves permission decisions to Claude Code.

- **Guard mode `minimal`, the new default:** Orchestra stops second-guessing Claude Code's permission mode. Generic command rules (destructive git, `rm`, force push, reset, branch-delete proofs, chained or malformed shell, PowerShell rules) no longer run outside autonomy. Orchestra keeps only what Claude Code cannot know: the autonomy and unattended locks, engine state and runtime protection, worker role limits and the approval-forgery check. `normal` and `protect` stay as opt-in modes.
- **No hook ever asks:** no Orchestra hook returns an ask, so no "Allow once" prompt comes from Orchestra in any mode. Protect mode's release check now denies and names the permit or the owner's `approved`.
- **Parallel waves checkpoint:** `orchestra.py waves` prints reservation overlaps, dependency chains, the waves and the cards startable now. `wave [--inline ID] ID ...` starts a whole wave in one step, all or nothing. `dispatch` and `inline` refuse a lone start while another disjoint card could start beside it; `--serial REASON` overrides and is logged. Policy `parallel_waves: false` turns the refusal off.
- **Live Kanban board:** `/orchestra-board` is a live pane with the columns queued, running, reported, repairing, held, parked and accepted. It refreshes on engine commands and worker events, links each card to its agent and Workflow run, and stacks the columns on a phone. `board --view` gives the same data as JSON without a lease and without hashing files.
- **Native task sync:** when the session exposes `TaskCreate`, `TaskUpdate` and `TaskList`, the board mirrors each card as a native task with status, owner and blocked-by, so the app's task list matches the coordinator's board.
- **Accepted work must land:** `report` records the commit named on the `ARTIFACT:` line, and `finish` refuses while accepted work is neither in HEAD nor patch-equivalent. The board shows `landed` per card.
- **Locks the audit found open, now closed:** while autonomy is active or the unattended lock holds, a shell write to Orchestra's state, a local move of the default branch (`git branch -f main`, `git update-ref`, switching to main and merging) and, when unattended, a tag delete are denied. A state file without a valid session no longer reads as no run.
- **The merge guard runs in every mode:** after `approved`, the printed merges are checked for order, head and form in `minimal` too.
- **Routine autonomous work:** `git commit ... && git push -u origin <feature>` is judged by its push, and deleting git-ignored files in the run repository is allowed.
- **Clearer output and refusals:** `wave --inline X Y Z` works as printed and names its workers; `status` and `review` drop per-file digests (`status --full` keeps them); refusals name the blocking card and the next command; task lists default to `[]`; `start` lists requeued cards; a malformed policy names its file; SessionStart says a run is live, and the Stop hook says why autonomy stopped.
- **Closed by the pre-PR review:** native task sync turns on only when `TaskCreate`, `TaskUpdate` and `TaskList` are all allowed without asking; under `minimal` the mod keeps reading autonomy status while autonomy is off, and the Python hook checks the lock state before it skips a mod-guarded call, so an arm from a terminal is enforced; a delete through an ignored symlink with a trailing slash (`rm -rf build/`) is checked at the folder the link points to.
- **Engine fixes found by using 2.13 on itself:** overlapping queued repairs no longer block each other (the lowest id starts first); after a review covers a builder report, the coordinator may correct only the command text of its `SELF_REVIEW` checks, and only while the reviewed files are unchanged.
- **Smaller fixes:** `NotebookEdit` is guarded; the mod marker follows `ORCHESTRA_STATE_DIR`; review packages under the state directory are writable; reviewer test-suite reruns stay a worker role limit in `minimal`, and heredoc text no longer counts as a suite run.
- **Working rules from the skill sources:** a builder lists each test, CI, timeout, snapshot or skip change on its own line; the final reviewer gives each such change a disposition and checks sibling call sites for each confirmed finding; a flaky test gets no retry, timeout or skip until its cause is named.

## 2.12.0 — 2026-10-23

Fixes for the friction met while using Orchestra to ship 2.11.0. None of them lets a card be accepted or a command run on less evidence than before.

- **A stale finding starts a repair:** `add` of a repair reads the newest receipt per category for the original, keeping a stale one, so a commit to other files no longer erases the finding the repair answers. A finding a newer CLEAN receipt superseded does not count. Acceptance still needs a current CLEAN fix re-review.
- **Fix re-review per chain:** a fix re-review that blames one chain no longer blocks accepting another chain it covers and does not blame.
- **Red-first checks:** a `SELF_REVIEW` check may carry `"expect": "fail"` (the failing run before the fix); it must be followed by a passing run of the same command.
- **`dispatch TASK [WORKER]`:** the worker defaults to `orchestra-<TASK>`.
- **Recording a review:** a receipt's `artifact` may be the string `"<sha> clean"` when the sha is a prefix of HEAD, the scope is clean and the policy is unchanged since the review card was dispatched; the engine stores its own record. `review FILE --token TOKEN` reports the review card, records the final receipt and accepts the card in one step.
- **Merged deletes:** `cd <path in this repository> && git push origin --delete B` and a trailing read-only `| tail`, `| head`, `| grep` or `| cat` are allowed for a merged delete; the merge proof runs in the `cd` target. A branch also counts as merged when every path it changed since its merge base holds the same entry on the default branch (`git diff-tree`, no merge driver runs), so a cherry-picked builder branch can be removed.
- **Build skill:** fast-forward a worktree to the brief's starting commit before editing; list a red-first run with `"expect": "fail"`; capture exit codes with `; echo EXIT=$?` on checks only.

## 2.11.0 — 2026-10-22

- **Fix, softening in compound commands:** in normal mode a softened item (wholesale add, `stash`, amend) no longer relaxes the other items of the same command; each keeps its own verdict. A softened command that holds a `#` comment or a `$'...'` string gets the strict verdict, because the split cannot read either.
- **Fix, `gh -R` / `--repo`:** the repository flag no longer hides a `gh` command pair from the guard; `gh -R o/r pr merge 7`, `gh --repo o/r release delete v1` and the like get the verdict of the flag-free command (the flag was a gap since 2.10.0).
- **Fix, guard readings:** `gh` flags written anywhere before or between the subcommand words (`gh --squash=true pr merge 7`, `gh pr --admin=true merge 7`, `gh -dRo/r release create v1`) no longer hide the command from the guard; and `<<` inside `$((...))` or `((...))` is a shift, never a heredoc opener, so `echo $((1<<x))` no longer hides the lines after it. A corpus test now checks that quoting, line continuation and extra `gh` flags keep every strict verdict.
- **Fix, line continuation:** a backslash-newline outside single quotes is joined before the guard reads a command, so `git \<newline>push --force` gets the verdict of `git push --force` (it was allowed). A quoted-delimiter heredoc body stays literal, as in bash, so a body line ending in a backslash no longer hides the next command.
- **Fix, unattended lock:** the lock reads provider deletes from the words as bash reads them, so a quoted or escaped word, a `find -exec` payload or a `gh` flag in any position no longer passes it.
- **Normal mode no longer blocks routine git work:** the new policy `guard_mode` defaults to `normal`, which warns or allows stash, wholesale `git add`, `commit -a`, amend, multi-ref and refspec pushes, and release actions without a question. `protect` keeps the strict verdicts and asks only while a run is active. An autonomous run, active or stopped with its report kept, is always strict. `classify` prints the strict verdict.
- **Autonomous runs open, review and approve pull requests:** the run pushes its own branches, stacks pull requests with `base TASK`, records them with `pr URL --task ID` and never merges to the default branch, deletes tags or releases. `complete` waits for a verified pull request.
- **"approved" runs the merges:** when the run has stopped, the owner types `approved` in the session. The `UserPromptSubmit` hook records a receipt and prints one `gh pr merge` command per pull request, in order and pinned to the recorded head. The merge guard allows only those commands. Until then a stopped run's report keeps an unattended lock: releases, merges, scheduler tools, settings edits and `start --new-run` stay denied.
- **Checks run locally, CI is manual:** `scripts/check.sh` runs every check; `.github/workflows/ci.yml` starts only by hand.
- **Guard and engine details:** the PreToolUse matcher now includes `CronCreate`, `ScheduleWakeup`, `RemoteTrigger` and `SendMessage`, and a call to one that carries only the word `approved` is denied in every mode. New policy keys `guard_mode`, `release_workflows` and `max_worktrees`; an unknown policy key is refused. A pre-2.11 ledger is refused at `arm` with a re-fill message. Known gaps and deferred live checks are in docs/BUILD-LEDGER.md.
- **Docs:** README, docs/hooks.md and docs/cli.md describe the modes and the approval flow; the coordinator skill gains `references/approval.md`.
- **Pre-PR review:** with policy `file_budget_bytes` set (off by default), `prepr` lists the changed files that grew past it against the run base, and the standards brief carries that list under `## Over file budget`; `file_budget_waivers` maps a glob to a reason.
- **Parallel work:** at most three worktrees at once; read-only side workers run beside inline work at any size; a medium run escalates once two disjoint units each reach about 600 lines; near the context ceiling the remaining units go to builders; `max_workers` is the owner's device and usage limit.
- **Worker results:** a short report is re-dispatched once, then recorded as an open gap; a dead worker gets at most two re-dispatches; the first of three or more similar tickets runs alone.
- **Failing gate:** the brief after a `gate-failing` stop names the gate's last log path.
- **Skills:** rules from Anthropic's code review posts, pstack and mattpocock/skills for briefs, triage, handoff, design, build, review and critic. Credits are in docs/SKILL-SOURCES.md.

## 2.10.0 — 2026-10-21

- **Autonomy band:** after a stop the band stays as `stopped: <reason>` until you re-arm, disarm or start a new session; before, the reason showed only as a toast and the band cleared. While active it also shows the running background workers, stalls above zero and any worker silent past `worker_stale_seconds`. `orchestra.py autonomy status` gains `running` and `silent`.
- **Idle on a lost worker:** the Stop hook that stops a `stalled` run runs only at the end of a turn, so a session idle on a worker that died was never checked. The band now shows the silent worker while you wait. The engine still decides nothing without a Stop event.
- **Review standards lens:** judge a change against HEAD (untouched debt is a note, not a blocker), name every suppression the diff adds, and read the repository's rules from the base commit.
- **Coordinator and critic:** own each worker result and send a redirected worker's whole scope to a fresh card; name the facts a change's safety rests on and prove each or report `unproven`. Credits for pstack, ratchet-files and the Code Review documentation are in `THIRD-PARTY-NOTICES` and `docs/SKILL-SOURCES.md`.
- **Packaging:** the marketplace entry no longer repeats the version (Claude Code reads `plugin.json` first and a second copy can only drift); the plugin has an icon; CI runs Claude Code 2.1.306.

## 2.9.0 — 2026-10-18

- **Session start:** the injected run brief leaves out empty sections (`### Needs you` with only `- none`), about 600 bytes per session.
- **Pull request pushes:** the destination must be the same branch name as the source (`git push origin feat/x`, or `feat/x:refs/heads/feat/x`); `HEAD:other-name` is refused with a reason that says so. A branch name with non-ASCII characters gets its own reason instead of the generic shape message.
- **Merged-delete check:** the whole check shares one 25 s deadline (the hook's timeout is 30 s). Past it the delete is denied with that reason, instead of the hook being killed with no answer.
- **PowerShell:** the PowerShell tool is now matched by the PreToolUse hook and its command is read with the same rules as Bash, so `git reset --hard`, pushes, deploys and the other classified commands are caught. PowerShell-only commands (`Remove-Item`, `Invoke-WebRequest`) are still not classified.
- **Windows gates:** a gate runs in a job object, so a process it leaves running is found and stopped after it exits, as on POSIX; the job also ends if the engine itself dies.

## 2.8.1 — 2026-10-18

- **Windows:** the Windows CI job (the whole test suite on `windows-latest`) now passes. The first run found one product bug and it is fixed: the engine tried to open the state directory to flush it, which Windows refuses, so every state write failed. The autonomy cleanup also accepts a drive-letter path (`git worktree remove C:/...`). The rest were tests that assumed POSIX (`/bin/sh`, `fcntl`, `os.getuid`, symlinks, deleting a process's working directory); they now use the portable layer or are skipped on Windows. Windows is still not checked on a real machine with Claude Code.

## 2.8.0 — 2026-10-18

- **Releases:** `docker push`, `podman push`, `terraform apply|destroy`, `tofu apply|destroy`, `helm install|upgrade`, `kubectl apply`, `pulumi up|destroy`, `twine upload`, `gem push`, `yarn`, `bun`, `poetry` and `uv` publish, and the `firebase`, `heroku`, `serverless`, `sls`, `cdk`, `sam` and `railway` deploys count as releases.
- **Guard messages:** the destructive Git denials name the safe alternative, and a command over 128 KiB says to write a file with the Write tool.
- **Autonomy:** a push to `production`, `prod`, `stable`, `live`, `release`, `releases`, `gh-pages`, `trunk`, `develop` or `development` is refused as well as the default branch; the default branch also comes from the remote's answer at arm, for both the merge guard and the merged-branch cleanup; `master` is tried when `main` is absent.
- **Silent workers:** a background worker with no report after `worker_stale_seconds` (policy, default 3600) is named in the next continuation; if nothing changes after that, the run stops as `stalled`.
- **Failing gates:** a required gate or ledger check that fails three times in a row stops the run as `gate-failing`, and the brief says which.
- **Large files:** files over 64 MiB are bound by size, mtime and their first and last megabyte, and their line count is estimated; before, every command read them whole.
- **README:** a one-time section for `CLAUDE.md`, `AGENTS.md` and trimming fixed context, with a script that lists what a session loads.
- **Windows:** the hooks and the CLI run on Windows with Git for Windows and Python 3.11 or later. File locks use `msvcrt`, a gate that times out is stopped with `taskkill /T`, the launcher tries `python` and `py -3` after `python3`, accepts a backslash script path and starts Python in UTF-8 mode, run state lives under `%LOCALAPPDATA%` unless `XDG_STATE_HOME` is absolute, and protected-path checks ignore case. The TypeScript mod stays inert on Windows paths, so the Python hooks guard every call there. CI runs the test suite on `windows-latest`.

## 2.7.1 — 2026-10-16

- **Finish:** a run that changed files needs a current final review even when it has no cards. `finish` used to accept 300 unreviewed lines.
- **Start baseline:** the files already modified or untracked when a run starts are recorded; the size warning and the review lenses count only what the run changes.
- **Evidence:** interpreter leftovers (`__pycache__`, `*.pyc`, tool caches, `.DS_Store`) are never evidence, so a gate that exits 0 no longer reports `passed: false` for them; a deleted file adds nothing to the fingerprint staged or not; tracked paths hidden by a sparse checkout are bound by their index mode and object id. Evidence still goes stale when anything moves, staging and committing included. After committing reviewed work, record the independent review again and `accept` succeeds: it needs the review to be current and the reported files unchanged, not the same HEAD.
- **Lost lease:** `start --recover --harness-session ID` gives the session that owns the run a fresh lease. The lease errors name it.
- **Blocked workers:** a report line `BLOCKED: reason` parks the card with the reason, so a worker that cannot do its card no longer has to fake a self-review.
- **Dropping cards:** `cancel TASK --reason TEXT` removes a queued or parked card that should never run.
- **Credentials:** `autonomy arm` records a digest of each remote's push URL instead of the URL, which can carry a token that `status` would print.
- **Small fixes:** `review` names the keys a report file is missing; a ledger saved with Windows line ends arms.

## 2.7.0 — 2026-10-16

- **Guards, scope:** changing Git aliases, push mappings, remotes and credential settings (`git config`, `git remote add|set-url|rename|remove`, `-c`) is a `config` boundary: it is denied only while autonomy runs and is an ordinary command otherwise. 2.6.3 to 2.6.5 denied it for every user.
- **Guards, speed:** a command with many heredocs is classified in one pass instead of one pass per heredoc.
- **Hooks, failure:** a crash in the PreToolUse hook, or a missing home directory, now denies the call with a message that names the cause, instead of allowing it. State falls back to a per-user directory in the system temp folder when no home is found.
- **Autonomy ledger:** while autonomy is active, edits to `autonomy.md` and `autonomy arm|disarm` run by an agent are denied, including through the TypeScript mod; `arm` refuses when autonomy is already armed. The owner disarms, edits and arms again.
- **Sessions:** a run bound to another session no longer locks a second session in the same repository out of Agent and subagent calls; its start-of-session note says so.
- **Unreadable state:** the denial names the state file and the way out, `start --new-run`, which now keeps the unreadable file under `history/unreadable-*.json`.

## 2.6.5 — 2026-10-15

- **Autonomy, pull request push:** `autonomy arm` records where each remote pushes to (`git remote get-url --push --all`, which applies `pushurl`, `insteadOf` and `pushInsteadOf`; a remote with more than one push URL gets no pull request push), and a pull request push is refused when that answer differs at push time. A changed remote URL or rewrite can no longer redirect an approved push, whichever setting or route caused it; this backs up the guarded-key list instead of relying on it. A state armed before this release has no record, so re-arm.

## 2.6.4 — 2026-10-15

- **Docs only:** `docs/BUILD-LEDGER.md` and `docs/VALIDATION.md` record the live checks run against the published 2.6.3 release: install from GitHub, the `deadline` stop, `clear` and `resume` rebinding, and the large route with one repair ending in `hold`. No plugin code changed.

## 2.6.3 — 2026-10-14

- **Autonomy, default branch:** `autonomy arm` now asks every remote for its current default branch, even when one is already recorded, and stores the answers in the run state (`remote_defaults`). The pull request push guard checks against those answers instead of the local `refs/remotes/<remote>/HEAD`, which could be stale after the remote changed its default. A remote that does not answer gets no pull request push until autonomy is armed again.
- **Autonomy, arming:** the remotes are asked before the armed state is written, so an `arm` interrupted during that step leaves autonomy off.
- **`pr URL`:** requires an http(s) URL with a host; `https:///pull/1` and similar are refused.
- **Releases:** `.github/workflows/release.yml` publishes a GitHub release for the plugin version, with the archives and their checksums. Push the tag `v<version>`, or run the workflow by hand from main, which creates the tag itself. It refuses a commit that is not on main, a tag that does not match `plugin.json` and a missing `docs/release-notes/v<version>.md`.
- **Gates:** processes a gate leaves running in its own process group are stopped when it exits; one that starts a new session or group is not tracked.
- **Guards:** a run cannot set or unset the Git configuration that routes or rewrites a push (aliases, `remote.*`, `url.*`, `push.*`, includes, `submodule.*`, `http.*`, `credential*`, `core.sshCommand`, `core.gitProxy`, `core.hooksPath`), and unrecognized `git config` forms and `git remote add`, `set-url`, `rename` and `remove` are refused; reading config and setting ordinary keys still work.
- **Mod markers:** a session start deletes the heartbeat markers of sessions that ended more than a day ago.
- **Permits:** documented that a release permit stays valid until the artifact changes or the session ends.
- **CI:** `.github/workflows/ci.yml` runs the generator check and the test suite on Python 3.11 and 3.13, and the strict plugin and marketplace validation plus the mod tests, on every pull request and on main. It lives in the repository, not in the installed plugin, and the release archive leaves it out.

## 2.6.2 — 2026-10-14

- **Pull requests in the brief:** `orchestra.py pr URL` (lease) records a pull request the run opened; every run brief lists it under Needs you as "review and merge pull request URL". The autonomy instructions record the PR this way instead of a free-form `progress.md` line.
- **Validation:** a full unattended autonomy run, from the first message to `complete`, is recorded in BUILD-LEDGER.md and VALIDATION.md.

## 2.6.1 — 2026-10-14

- **Autonomy:** `autonomy arm` records each remote's default branch where it is missing (`git remote set-head <remote> --auto`, outside the state lock, 20 s per remote) and reports it as `remote_heads` in the preconditions. A remote it cannot reach is reported and arming still succeeds; pull request pushes to that remote stay refused until its default branch is known. No manual `set-head` step before arming.

## 2.6.0 — 2026-10-14

- **Autonomy loop:** the Stop hook continues a turn only when the coordinator can act now (a ready or reported card, an open final finding, a held chain owed its final review). Running workers alone let the turn end; the harness wakes the session when one finishes. Once every card is accepted it continues into the final review, gates and pull request. A continuation is never sent twice for an unchanged progress signature: that turn ends as a stall, and a stall with no worker running stops the run with the new reason `stalled` (nothing would wake it). Before, every Stop while workers ran re-sent the same prompt.
- **Relaunch removed:** `orchestra.py relaunch`, `autonomy arm --relaunch`, `autonomy settle` and `config/relaunch-prompt.md`. Passes could only run foreground workers, and the context-ceiling rule had no signal. A 2.5 state carrying the flag loads, and its autonomy is dropped when a new session opens over the inactive run; re-arm in a live session.
- **Guards: ask instead of block:** during an interactive run, a release action (`git push`, `gh pr merge`, `gh release create`, package publish, deploy) runs with a current engine permit and otherwise raises Claude Code's approval prompt, instead of being denied. A release inside a multi-command line asks too. Because a mod `tool.call` hook cannot ask, the Python hook no longer takes the fresh-marker shortcut for release commands.
- **Guards: autonomy opens pull requests:** under autonomy, a plain push of one feature branch (not the remote's default branch, `main` or `master`) is allowed, and `gh pr create` already was. Merge, other releases, default-branch pushes and deletion stay denied and park the card; the owner merges after the run. The ledger's fixed Push line is now `- Push: push only a feature branch for a pull request; never the default branch.`; a 2.5 ledger's `no push to any branch` line still arms.
- **Autonomy cleanup:** under autonomy the coordinator may delete a branch (`git branch -d|-D`, `git push <remote> --delete`) or remove a linked worktree (`git worktree remove` without `--force`, `git worktree prune`) when the branch is provably merged into the default branch. Each runs as a plain single command. `rm` and every other deletion stay denied.
- **Autonomy pull request push tightened:** only `git push [-u|--set-upstream] <remote> <refspec>` with a configured remote name (no `remote.<name>.push` or `pushurl`), a local branch as source and one destination branch other than the remote's default branch, `main` or `master`, compared case-insensitively. The remote's default branch must be known locally (`git remote set-head <remote> --auto`).
- **Release classification:** `gh api` calls that mention merge (a `pulls/N/merge` call or a `mergePullRequest` mutation), a `gh api graphql` call with a mutation or a request body the guard cannot read (`--input`, a `=@file` field), and `cargo publish` are release actions.
- **Hooks:** the PreToolUse timeout is 30 seconds. Without Python 3.11 or later, `run-hook.sh` fails PreToolUse closed (exit 2) and only warns on every other event; it probes each candidate interpreter, so a broken pyenv shim is skipped. A relative `XDG_STATE_HOME` is ignored.
- **Release archive:** `scripts/build_release.py` leaves out tests and development files. Its private-content scan also catches Linux home paths, `github_pat_`, Slack `xox` tokens and AWS `AKIA` keys.
- **Engine hardening:** task JSON can no longer set engine-owned fields; a stale review with findings blocks `accept`; `start --policy` validates the file; CLI errors exit 2 with JSON. A 2.5 state armed with `--relaunch` no longer re-arms on `start`.
- **Docs:** the turn ends while background workers run; open the pull request before `complete`; fix re-review briefs need no `Lens:` line; the standards lens uses `code-reviewer-standards`; ending the session ends autonomy only for a `--harness-session` run; README uninstall steps.
- **README:** rewritten end to end: install, the run from first message to completion, one roles table with subtypes, the guard modes, autonomy, commands and condensed upgrade notes.
- **Context:** the triage escalation no longer cites a percentage of the window. The README recommends `autoCompactWindow` in the user's Claude Code settings.

## 2.5.1 — 2026-10-10

- **Engine:** a run state whose session carries `size` never loads under the 2.3 policy hash. Before, `binds()` refused only a session with `items`. The two task-size checks share one constant, `CARD_SIZES`.
- **Examples:** `examples/global-CLAUDE.md` (a user-level `~/.claude/CLAUDE.md` that routes through Orchestra) and `examples/project-AGENTS.md` (a project charter whose standing orders Orchestra pastes into every brief).

## 2.5.0 — 2026-10-09

Route by diff size instead of item count. The design is `docs/DESIGN-v2.5.md` (owner decisions D1 to D5), the contract is `docs/PLAN-v2.5.md` section 2.

- **Size tiers (D1):** `start --size tiny|medium [--asks N]` is required for a new run. Tiny is up to 50 changed lines (inline edit, no alignment; a tiny builder card needs `dispatch --helper REASON`), medium up to 400 (grill inline, then every unit inline in sequence; the medium benchmark showed a worker's fixed cost exceeds a medium unit's inline time). Large runs 2+ units through Workflow builders, and the coordinator starts its own inline card in the same turn. `--asks` counts separately stated asks; the tier is the largest ask and the budget is the guide times the count.
- **Large only by escalation:** `route --size large --reason TEXT`, or `start --size large --owner-request` when the owner asks for a map. A designer-planner plan card needs a large run or an owner request.
- **Size check (D2):** the new read-only `prepr` command compares the diff with the budget and prints a warning; it never blocks.
- **Reviewer by summed diff (D3):** `prepr` names the pre-PR reviewer: Sonnet 5.5 (`code-reviewer-medium`) up to 400 changed lines, one card with `Lens: combined`; Opus 5.5 with one card per lens above 400.
- **Wayfinder (D4, D5):** `references/wayfinder.md` maps large work as decision tickets in `docs/maps/<name>.md`; research tickets run together as investigator cards. Derived from mattpocock/skills at 49dd158d1076 (third pin, credited).
- **Engine gaps:** `gate --timeout SECONDS` overrides the policy timeout for one run. A reported card takes a replacement report from the same worker until accept or a review covers it, so a wrong report no longer needs park and unpark. A builder report needs a nonempty `ARTIFACT:` line, so a report cannot be accepted with no commit named.
- **Upgrade:** a 2.4 run loads under 2.5 and keeps item routing; `start --items` is refused (README, Upgrade from 2.4 to 2.5).

## 2.4.0 — 2026-10-08

Inline-first routing, builder self-review and one review before the PR. The decisions are `docs/PLAN-v2.4.md` section 1 (S1–S11), the contract is section 2.

- **Model matrix (S1, S2):** Haiku 5.5 high for mechanical and cleanup builders, operator and code discovery; Opus 5.5 only for critic (high), final reviewer and builder repair (medium).
- **Routing (S3, S11):** `start --items N` is required for a new run; 1 to 5 items run inline (`dispatch --helper REASON` for a helper builder), 6 or more go through a designer-planner plan card and Workflow builders. `route` changes the route mid-run.
- **Self-review (S6):** a builder report carries one `SELF_REVIEW:` JSON line with its checks and criteria; the engine accepts a builder card on it while the artifact is current.
- **One review before the PR (S4, S5, S7):** checkpoint review, waves, gates between waves, `supersede` and the `code-reviewer-checkpoint` agent are removed. Only the pre-PR review and one fix re-review are recorded; a chain still blocked after that is held. Lenses come from the diff: security on `sensitive_paths`, standards above `standards_min_lines`.
- **Guards (S9, S10):** during a run the main session may start only `orchestra:*` agents (denied also when the run state cannot be loaded), and shell, edit and agent calls from any other agent, including agents a Workflow starts, are denied (file reads are not guarded). Reviewers and critics cite a current gate receipt instead of rerunning a test suite.
- **Upgrade:** a 2.3 run loads under 2.4 with 2.3 routing; its gate and review receipts go stale (README, Upgrade from 2.3 to 2.4).

## 2.3.0 — 2026-10-06

Four small items folded from mattpocock/skills at 2b47ffcf2385 (second pin; credited in `plugins/orchestra/THIRD-PARTY-NOTICES`).

- **Strategic track:** the coordinator works a tactical track (finish the task) and a strategic track (change the environment so the next task goes better: a lint rule, a constrained API, a standards file or a check, not more instructions). `coordination.md`, section Two tracks.
- **No workarounds:** a deviation from project convention is fixed, as its own card, before feature work builds on it.
- **Bug-lane retro:** after an accepted repair, name the missing check or seam that would have caught the bug and route adding it.
- **Handoff directory:** `handoff.md` names the temporary directory: `$TMPDIR`, else `/tmp` (`%TEMP%` on Windows).

## 2.2.0 — 2026-10-05

The full change set is `docs/SPEC-v2.2.md` section 5; each item below names its section.

- **Wave review and repair-diff check (5.1):** one checkpoint review per wave over its reported tickets; a repair is checked against its own diff before the chain tip is accepted (`repair_check`, `supersede`, wave labels in `status`).
- **Repair ladder ending in hold (5.2, 5.3):** a builder gets one repair; a chain still blocked after it is held (`hold`), its work stays in place, the held log records it and the run continues. Held dependencies count as satisfied.
- **Gates between waves (5.4, 5.11):** gate receipts are recorded once and reused; a repeated gate needs `gate --again`; boundary gate argv is refused.
- **Final phase (5.5):** three parallel lenses (correctness and security on Opus 5.5 high, standards on the new Sonnet 5.5 medium `code-reviewer-standards` variant). Final receipts attribute findings to chain tips and must address every held tip. The final repair loop has no round cap.
- **Materiality (5.6):** review reports separate blocking `findings` from `issues`; work with no real impact, or under about 20% impact on otherwise-correct work, is a note, never a failure.
- **Out-of-scope triage and findings ledger (5.7, 5.12):** out-of-scope defects never change a verdict; they are triaged inline, as a card or in the brief.
- **Autonomy without caps (5.8):** the deadline is the only limit; `max_passes` and `max_stalls` from 2.1 ledgers are recorded but not enforced. Stalls are detected by signature. The status band reads "pass N". A ledger `Release:` line pre-authorizes one exact remote and target pair.
- **Run brief (5.9):** every end path appends one `## Run brief` to `progress.md`; `brief` prints it.
- **Relaunch harness (5.10):** `orchestra.py relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]` runs fresh-context passes until `complete`, `deadline` or a stop, with `settle` before each pass and a pass session nonce. A signal disarms autonomy without taking the state lock in the handler.
- **Briefs carry exact keep and remove lists (5.13).**
- **Guard (5.14, 5.15, 5.16):** forced deletion of a branch that is provably merged into the default branch is allowed (local and remote; the remote push URL must equal its fetch URL; default refs and the branch name are matched exactly, case included). Raw ref deletion through `git update-ref` is denied. Abbreviated long options are read as git reads them; `commit --amend` is denied. Hook state reads wait at most 2 s; a busy lock or a removed session directory denies only the delegated classes, with a reason. The mod's fail-closed message names its failure class, and `delegate` spawns from the plugin root. The chained-command failure reproduced at the mod seam (missing session directory); the fix ships here.
- **Engine (5.17):** read-only reviews no longer collide with the cards they review.
- **Mixed versions on one active run (section 8):** a 2.1 engine reading 2.2 state rejects any `held` card and an armed autonomy without `max_passes`, and the 2.1 hooks then fail closed for that run. End every 2.1 session before the first `hold` or before arming autonomy under 2.2.

## 2.1.0 — 2026-10-05

- Claude-native only. Removed the Codex package (`plugins/orchestra-codex`), `.agents`, the Codex manifest and hook file, the generated worker profiles, `install-profiles` and `uninstall-profiles`, and every Codex path in the engine, hooks and generator. `config/models.json` keeps only the claude profile. Claude roles, models and efforts are unchanged; `agents/*.md` are byte-identical to 2.0.1.
- Stricter Git guard, in both the Python guard and the TypeScript mod, kept in parity by the shared corpus: every `git stash` form is denied (including `list` and `show`); wholesale `git add` is denied (`-A`, `-u`, `--all`, `--update`, `--no-ignore-removal`, short clusters with `A` or `u`, and the pathspecs `.`, `./`, `..`, `../`, `:/`, `:/.` and `*`); `git commit -a`, `--all` and clusters with `a` are denied. Commit messages that merely mention these words stay allowed.
- Docs and skill references rewritten for Claude only. Historical records are unchanged.

## 2.0.1 — 2026-10-04

- Claude `PreToolUse` matcher now includes `Agent` and `Task` (`Bash|Edit|Write|MultiEdit|Agent|Task`), so workers cannot delegate in Claude Code. This supersedes the 2.0.0 note that the matcher covered only `Bash|Edit|Write|MultiEdit`.
- Test: `_MOD_TOOLS` in `orchestra_core/hooks.py` must equal `GUARDED` in `hooks/mod/orchestra.ts`, so the two lists cannot drift apart.
