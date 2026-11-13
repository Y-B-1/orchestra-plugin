# Ticket plan

Plan only: edit no code and settle no product question.

## Start gate
Start from the approved spec, the repository facts and the binding project rules. If the brief names no approved spec, or a ticket depends on an open decision, mark that work blocked. Compare the plan with each binding rule before slicing and again when finished. When the brief names an issue, spec path or URL, read its full body and its comments before slicing.

## Slice
1. Map the files and resources touched and what each is for. Group what changes together.
2. Cut vertical slices: each a narrow, complete path through every layer it needs, checkable alone, small enough for one fresh context. The first is the thinnest end-to-end slice. For work judged by comparison (migration, parity, speed), the first ticket records the baseline and the comparing check.
3. Split a ticket with more than three build items in one file.
4. Exception, a wide mechanical change (rename, retype across many callers): expand (new form beside old), migrate in batches by blast radius, then contract (delete the old). Each batch is blocked by the expand; the contract by every batch. If even the batches cannot stay green alone, let them share an integration branch and block one final integrate-and-verify ticket that alone promises green.
5. Class each slice: spike (throwaway, answers one question, never merged), bounded (flow exists), architectural (new subsystem or shared interface, ordered first).

## Each ticket
Goal, class, role and mode; starting artifact; owned paths and named shared resources; blockers by ticket; acceptance criteria with the scoped commands; what the report must show. Copy each binding rule into the ticket, since a link does not reach an empty context. Give tests a name and assertions and code its exact signature and file; write a body only where signature and tests leave an algorithm open. "Handle edge cases" decides nothing: strike it. Check each acceptance criterion against the base commit: it must fail there, and this ticket alone must be able to make it pass. A prototype snippet that states a decision more exactly than prose may ride in the ticket, marked and trimmed. A ticket that outlives the run names behaviors, interfaces and acceptance checks, not file paths or line numbers.

## Graph
- Two tickets editing one resource share an owner or one blocks the other.
- Check cycles and unknown blockers. Each queued ticket must become ready from its accepted blockers alone. Independent tickets start together; plan the widest first wave.
- For each consumer of an earlier ticket's output, write one row: both tickets, what is produced against what is consumed, the finding. Rule conflicts against the spec.

## Group
Group tickets into PRs, each one change a reviewer reads alone. Tickets with intersecting files share a worktree; one writer or writers in sequence use none; concurrent writers on disjoint files share the checkout.

## Reviews
Name the checks to run and each live check (a human step: write exact steps). One review covers each PR. Say where a blocked finding returns each ticket.

## Publish
Write one file per ticket, or one issue per ticket in dependency order, whichever the project uses. Return the breakdown (title, blockers, what it delivers) in your report; the main session confirms granularity and blockers with the owner before publishing, unless in a goal. On a tracker, the main session:
- Checks the target repo first (`orchestra:ship`, top section); pass `--repo`.
- Checks each label exists (`gh label list`). It creates one with `gh label create` or publishes without it and says so; a missing label never stops a set halfway.
- Publishes blockers first. On GitHub use `gh issue create --blocked-by <n>` or `gh issue edit --add-blocked-by` and `--add-sub-issue` (recent `gh`; check `gh issue create --help`). On an older `gh`, POST to `repos/<o>/<r>/issues/<n>/dependencies/blocked_by` with the blocker's numeric database id (`gh api repos/<o>/<r>/issues/<n> --jq .id`), never its number. Count open blockers with `.issue_dependencies_summary.blocked_by`.
- Applies `ready-for-agent`, and never closes or edits the parent.
- Appends each published issue's URL to the ledger and searches the tracker before it creates one, so a retry never files a ticket twice. Wire cross-references with real numbers, never a placeholder.
