# Project verification driver

Goal: one command that starts the real app, exercises a flow the way a user does, and prints evidence. Write it for an agent that reads it cold.

## Build
1. Answer from the repo, ask the owner only for what you cannot observe: the surface a user touches (web, CLI, API, desktop, mobile), the start command (package scripts, Makefile, README), ports, env vars, seed data, auth.
2. Reuse what exists first: Playwright or Cypress specs, expect or PTY helpers, curl-able endpoints, a debug port. Only then pick a generic path: browser for web, tmux or PTY for a CLI, plain HTTP for a service.
3. Keep it in the repo, next to the repo's other test tooling, in the repo's language. Name the one command in the README or the package scripts.
4. The driver has these parts:
   - Launch: start from an empty data dir, including migrations and seed data. Ready means usable (a page renders, a query answers), not that a port is open. For a short-lived CLI, build once and start each drive in its own isolated session.
   - Doctor: one read-only check that the instance is worth driving: process up, right build, port owned by us, auth valid.
   - Drive: real selectors, commands and routes from this repo. Prefer stable handles (ARIA label, data attribute, prompt text, route) over coordinates and tab order.
   - Evidence: the action and the resulting state, plus side effects (rows, files, messages). Use the real user path, never an internal setter or a test-only endpoint. Mock only where a production boundary already isolates the outside system. Learn what a dry-run skips by observing files, network and refs, not by trusting its name.
   - Cleanup: stop what the run started. Keep the evidence in a named location.
5. Isolate: if two instances cannot run side by side (shared port or data dir), say so in the driver and refuse to drive a shared instance.
6. A missing asset that blocks startup and is irrelevant to the flow may be created, marked as verification scaffolding, and removed in cleanup.
7. Run it end to end once. After cleanup, confirm the evidence still exists. Run cleanup after every failed attempt so no process or port is stranded.
8. Seed a feature map, one file per user-facing feature: how to reach it, how to drive it, the end state that proves it, and gotchas. A proof that drives one entry point is incomplete when the map lists others.
9. A proof run in a stand-in (container, local stack) lists each setup step the real target will not get.

## Maintain
Do this when a change touches a flow the driver covers, and on a stale driver you meet.
1. List the flows the driver covers. Check each against source for drift: a renamed route, a moved selector, a changed command.
2. Run the driver live, once per flow. Source that looks clean does not replace a live run.
3. Sort each finding: wrong or missing description or step is drift, fix the driver. Working behavior the driver cannot reach is a harness gap, fix the driver. Behavior that is actually broken is a product bug: report it, do not hide it in the driver.
4. Edit only the driver and its docs in this pass. Report one of: clean (nothing to change), changed (what you fixed, with the run output), blocked (what stopped you).
5. Run doctor again after any failed drive. Report a feature as unreachable only with its concrete prerequisite and the route you tried.
