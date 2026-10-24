# Field report: coordinator lease loss and coordination friction (2026-10-25)

Source: one long coordinator session (Orchestra 2.13.1, then 2.14.1) running a multi-week build with about 150 cards
and many parallel builder workers in one worktree. Everything project-specific is removed: no repo paths, card ids,
lease values or company names. Command lines keep their real shape; `<LEASE>`, `<REPO>`, `<ID>` and `<TOKEN>` are placeholders.
Where a cause is a guess, this report says so.

## 1. BLOCKER: `accept` (and probably every state change) fails after the session restarts

Symptom, after a context compaction and a session restart (same conversation, same repo, same lease value):

```
$ orchestra.py --repo <REPO> --lease <LEASE> accept <ID>
{"error": "Invalid or interrupted coordinator lease. If this session lost its lease, take it back with `start --recover --harness-session ID` (the id is in the SessionStart context)"}
exit 2
```

Facts:

- Read-only commands still work with the same lease: `board`, `status`, `waves`.
- Same error on 2.13.1 and on 2.14.1 (run against the same state directory).
- `status` shows autonomy off (`active: false`, `last_stop_reason: parked-only`). Autonomy is not the cause.
- Only `accept` was tried after the break. `report`, `wave` and card creation are expected to fail the same way; not tested.
- Cause (guess): the lease is bound to the harness session id; the restart ended that session and the engine marked the
  lease interrupted. Nothing revives it by itself.
- A forked session gets a NEW harness session id. Its SessionStart text offers `--harness-session <new id>`, but the
  lease belongs to the old id. Recovering from the fork would take the lease from the original session. The refusal
  does not name the owning session, so the user cannot tell which id to pass.

Conflict between two instructions, both emitted by Orchestra:

- SessionStart context: "do not repair the repository, resume prior runs or arm autonomy without an explicit request".
- The error text: "take it back with `start --recover`".

A coordinator that was told to continue an existing run cannot tell whether `--recover` counts as "resuming a prior run".
It stopped and asked. That cost a full user round trip for a state change that arms nothing and releases nothing.

Suggested fixes:

1. A restart of the same conversation (same repo, same lease holder) renews the lease without a manual step, or
   `accept` and `report` fall back to read-only plus a clear "run `start --recover`" line that includes the exact
   command with the right id.
2. The refusal names the lease owner (harness session id) and says whether it was interrupted or replaced.
3. Say in the SessionStart text that `start --recover` of your own lease is allowed and does not arm autonomy.
4. Define fork behaviour: a fork either reads only, or asks before taking the lease.

## 2. `wave` refusals do not say which card or resource conflicts

```
{"error": "Task is not ready or capacity is exhausted: its files or resources overlap a running, reported or repair card"}
```

One message covers: card not ready, worker capacity full, file overlap, shared-resource overlap, and a reported but not
yet accepted card still holding ownership. The coordinator had to open card JSON files and compare `files` and
`resources` by hand to find the cause. Please name the blocking card and the reason (`capacity 3/3`,
`resource intpg held by <ID>`, `files overlap <path> with <ID>`, `dependency <ID> not accepted`).

## 3. `waves` / `startable_now` lists cards that cannot start together

Two cards that declare the same resource (`intpg`, a single local database slot) were both in `startable_now`.
`wave A B` then failed with the message in section 2. Only `wave --serial "<reason>" A` worked. `startable_now` should
group cards by shared resource, or mark which subset can start in one wave.

The same happened with three lint cards that share a lock resource: the plan showed three waves of one card each
but the listing did not say they were serialised by a resource.

## 4. A reported card keeps its resources until accepted; combined with section 1 this deadlocks the queue

A card that has reported still holds ownership and resource slots. Queued cards that need the same resource cannot
start until the reported card is accepted. If `accept` is blocked (section 1), the whole queue behind it is blocked too.
Consider letting a coordinator release the resource slot at `report` for read-only checks, or document the expected
recovery path.

## 5. Recording coordinator evidence on a failed self-review criterion has no supported command

A builder `SELF_REVIEW` with a criterion marked `met: false` blocks `accept`. The coordinator had a legitimate reason to
accept (the criterion was out of the card's scope, or a bypass was named and logged). The only way found was to edit the
saved report text with a script and call `report` again. Please add something like
`orchestra.py criterion <ID> "<criterion>" --evidence "<text>"` that records coordinator evidence and keeps an audit line.

## 6. `close_inline`-style reservation is not atomic

An inline card reserved with `inline <ID>` returned a token, then the follow-up report step failed because the report file
was not there yet. The card stayed reserved. The token had to be reused with a raw `report main <TOKEN> <FILE>` call.
Please make reservation and report one step, or make a failed first report release the reservation.

## 7. Validation messages should list the valid values

- A card with size `small` was refused. The message did not list the valid sizes (`medium` worked).
- A builder brief without a `## Remove` heading was refused; the heading list should be in the message.
- A brief without a `Mode:` line matching the card mode was refused (this message was clear).

## 8. `cancel` works only on queued or parked cards, with no hint

`cancel` on a card that was not parked returned an error. The sequence `park`, then `cancel`, worked. The error could
say "park the card first".

## 9. A running card cannot be given one more file

A builder found it needed seven `export` keywords in a file it did not own. The only path was to cancel the card and
create a new one with a wider list. A coordinator-approved `own add <ID> <path>` for a running card (subject to the same
overlap check) would avoid the loss of the worker's half-finished work.

## 10. Workers leave scratch files in the worktree; ownership checks find them late

Workers cannot delete files (`rm` is blocked by the guard) and wrote scratch files, probes and `.orig` copies into the
owned worktree. They were found only by a manual ownership check after the report. Suggestions: a per-card scratch
directory outside the worktree in the brief by default, and an automatic "files changed outside the owned list"
check at `report` time that blocks or flags the report.

## 11. `status` output is too large to use

`status` printed about 1.6 MB of JSON on a run with 150 cards. It was unusable in a terminal. Please add `status --brief`
(counts per state, running cards with owner and age, lease holder and state, autonomy state) and make `--json` opt-in.

## 12. Background workers die with the session and leave no marker

Workers started through the Workflow tool are stopped when the session ends. The notification said the task "didn't
finish before the previous session ended", with no indication of which card, whether it had written a report, or
whether files were left half-edited. After a restart, `start` requeues running cards, but the coordinator also needs a
per-card "last known state of its worktree files" line.

## 13. Shell guard messages do not say what triggered them

Messages like `BLOCKED: ambiguous commit candidate: compound or future-mutating command` appeared on read-only chains
(`git log ...; python3 ...`, a heredoc with expansion, a `git diff` piped to another command). The message did not say
which part tripped the rule. This guard may be project-level and not part of the plugin; reported here in case it is.
If it is the plugin's, please name the matched token and suggest the allowed form.

## 14. Stale run brief at SessionStart

The run brief injected at SessionStart showed an old state (`parked-only`, `passes: 0`, a card named "blocked as described
above" with the description missing) while the live board had over 140 accepted cards and active work. A brief that is
that stale makes the coordinator doubt which state is right. Suggest printing the brief's age and the live counts side
by side, or regenerating at SessionStart.

## 15. Many plugin versions share one state directory

Nine cached plugin versions exist. A command run with 2.14.1 used the state written by 2.13.1 without a migration
notice. It worked for read-only commands and failed the same way for `accept`. Please print the state schema version
and the engine version on `status --brief`, and say if an older engine wrote the state.

## Prompt for the fixing session

> Read `docs/field-reports/2026-10-25-lease-and-coordination.md`. Fix section 1 first (lease renewal on restart,
> refusal text names the owner, fork behaviour, SessionStart wording). Then sections 2, 3, 5 and 11 (they cost the most
> time). Add a test for each: a lease interrupted by a session restart can be recovered without arming autonomy; a
> refused `wave` names the blocking card; `startable_now` never lists two cards with a shared resource in one wave;
> `criterion` records evidence and an audit line; `status --brief` stays under 4 KB for 150 cards. Do not touch release
> permits. Report with command output.
