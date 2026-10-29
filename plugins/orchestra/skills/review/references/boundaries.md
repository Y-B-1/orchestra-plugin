# Boundaries and idempotency lens

## Boundaries
- Validate, narrow and handle errors where data crosses in: CLI args, config, network, external APIs, files. Inside, trust the types.
- Flag re-validation deep in a call chain when the boundary already validated. Flag missing validation at a boundary.
- Business logic sits in pure functions. Framework wiring, handlers and adapters stay thin so logic tests need no framework.
- Do not expose transport, storage or framework types through the public surface. Expose domain concepts.
- General mechanism lives inside; special-case policy lives at the edge.
- Two tests: Is this data crossing a boundary now? Can the shell just call a pure function here?

## Idempotency
Apply to commands, migrations, jobs, webhooks, lifecycle steps and loops that run under crashes, restarts and retries.
- Run twice in a row: same end state? A retry must not repeat a side effect (a charge, an email, a row).
- Crash at every point: what is left behind? A lock, temp file, half-written record or claimed job must be recognizable as stale by the next run. A marker the next run cannot judge turns each crash into manual cleanup.
- Does the step read current state, compare to the goal and apply only the difference? A step built from "what the last run meant to do" is fragile.
- Concurrent runs: a check-then-act without a unique key, lock or compare-and-set.
- Expect a finding to name the crash point or the second run that breaks it.
