# Measurement lens

Use when the diff or the author's report claims a speedup, regression, throughput, latency or eval score. A number with no evidence is unproven, not a pass.

## Before you judge
- Write the claim in the words it would ship in ("export is 30% faster at p50 on 60k rows"). Each check below tests that sentence.
- Read the measurement script. Note what it times, counts and ignores.
- Note machine load (`uptime`) and core count. A busy machine needs interleaved runs, and the report says so.

## Seven checks (answer from a run or a trace, not from reading the code)
1. Why not double? Name the limiter (a core, a lock, disk, network, the load generator) from a profile or counters, mapped to source. Cannot name it: inconclusive.
2. Tuned? Every side runs as production runs: release build, production flags, warm or cold caches as in production, same data and versions. A side on defaults compares settings, not implementations.
3. Past a limit? Check bytes per second against bandwidth, operations against cores. Removing a piece that is 10 percent of a run speeds it at most about 11 percent. A result past a limit measured something else.
4. Errors? Count failures and wrong outputs. Rejections are fast and timeouts are slow, so errors distort a mean.
5. Reproduces? At least five runs per side, alternating A B A B. Report median and range. A gap inside run-to-run spread is no difference.
6. Matters? Compare the micro result to the end-to-end path a user waits on, with realistic size and concurrency.
7. Happened? Confirm the work ran inside the timed region. Lazy generators, unawaited promises, discarded results and timeouts give numbers for work that never ran.

One run is enough only for a ballpark the user asked for. Still do checks 4 and 7 and say it is one run. Choosing between options is never a ballpark.

## Reporting
- Lead with the verdict: faster, slower, no measurable difference, or inconclusive.
- Give the number with unit, run count, range and limiter: "p50 41 ms to 33 ms, median of 7 runs per side, range 32 to 35, bound by JSON parsing on one core."
- Inconclusive when you cannot name the limiter, a side ran untuned, or checks 4 or 7 could not be done. Name the gap.
- For an eval result ask the same: did each trial do the task, does the gap hold across trials, does the scenario matter.
- Keep one primary number in a PR body. Runs and evidence go in a linked note.
