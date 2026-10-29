# Ticket plan

Plan only: edit no code and settle no product question.

## Start gate
Start from the approved spec, the repository facts and the binding project rules. If the brief names no approved spec, or a ticket depends on an open decision, mark that work blocked. Compare the plan with each binding rule before slicing and again when finished.

## Slice
1. Map the files and resources touched and what each is for. Group what changes together.
2. Cut vertical slices: each a narrow, complete path through every layer it needs, checkable alone, small enough for one fresh context. The first is the thinnest end-to-end slice. For work judged by comparison (migration, parity, speed), the first ticket records the baseline and the comparing check.
3. Split a card with more than three build items in one file.
4. Exception, a wide mechanical change (rename, retype across many callers): expand (new form beside old), migrate in batches by blast radius, then contract (delete the old). Each batch is blocked by the expand; the contract by every batch.
5. Class each slice: spike (throwaway, answers one question, never merged), bounded (flow exists), architectural (new subsystem or shared interface, ordered first).

## Each ticket
Goal, class, role and mode; starting artifact; owned paths and named shared resources; blockers by ticket; acceptance criteria with the scoped commands; what the report must show. Copy each binding rule into the ticket, since a link does not reach an empty context. Give tests a name and assertions and code its exact signature and file; write a body only where signature and tests leave an algorithm open. "Handle edge cases" decides nothing: strike it. A ticket that outlives the run names behaviors, interfaces and acceptance checks, not file paths or line numbers.

## Graph
- Two tickets editing one resource share an owner or one blocks the other.
- Check cycles and unknown blockers. Each queued ticket must become ready from its accepted blockers alone. Independent tickets start together; plan the widest first wave.
- For each consumer of an earlier ticket's output, write one row: both tickets, what is produced against what is consumed, the finding. Rule conflicts against the spec.

## Group
Group tickets into PRs, each one change a reviewer reads alone. Tickets with intersecting files share a worktree; one writer or writers in sequence use none; concurrent writers on disjoint files share the checkout.

## Reviews
Name the gate sets and each live check (a human step: write exact steps). One review covers each PR. Say where a blocked finding returns each ticket.

## Publish
Write one file per ticket, or one issue per ticket in dependency order, whichever the project uses. Show the owner the breakdown (title, blockers, what it delivers) and ask if granularity and blockers are right before publishing, unless in a goal. On a tracker, publish blockers first, set native blocking links where the platform has them, add each ticket as a sub-issue of the source issue, apply `ready-for-agent`, and never close or edit the parent.
