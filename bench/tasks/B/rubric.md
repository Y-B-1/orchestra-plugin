# Task B rubric

Score each ask 0 to 2: 2 = done as asked and checked (its hidden tests pass, diff matches the spec); 1 = partly done or done with a visible flaw; 0 = missing or broken.

| Ask | 2 points when | Typical 1 |
| --- | --- | --- |
| B1 Open P&L | Card text, card accessible name and column renamed | aria-label left as "Unrealized P&L" |
| B2 Day change | Column after Price, signed whole dollars, totals row aligned with the total | Totals row misaligned (colSpan not updated) or no total |
| B3 AUM | "AUM" prefix, up to two decimals, KPI cards unchanged | Global compact format changed so KPI cards change too |
| B4 tier labels | One shared label helper used by list, drawer and client page | Capitalized with CSS or duplicated maps |
| B5 tokens | Two token values changed in theme.css | Values hard-coded elsewhere |
| B6 report counts | Counts on every tab via the Tabs badge, correct numbers | Counts only on some tabs or computed per tab with extra fetches that flicker |
| B7 pager bug | `pageCount` fixed, unit test covers an exact multiple | Page component patched around the wrong count |
| B8 stale search | Superseded responses ignored (cleanup flag or useAsync), unit test, cause explained | Debounce raised or latency changed to hide the race |
| B9 page names | One module drives sidebar, top bar and tab title; per-page title calls removed; instrument symbol in both | Titles fixed for the failing pages only, second map kept |
| B10 tests | Duplicates gone, skip deleted, snapshot replaced by a visible-output check and file removed, useAsync fixed without a disable and lint clean, new tests lean | Snapshot test deleted without replacement, or the disable swapped for another suppression |
| B11 client page | All listed parts present, notes shared (same storage key), unknown id handled, unit tests | Missing pager, notes copied to a new key, or no tests |
| B12 rebalance | Defaults, maths, rounding, validation, reset, unit tests for the maths | Floating cents shown, validation missing, or maths only inside the component |
| B13 docs | README covers client page, rebalancing, routes and the names module | Partial |

Quality points (0 to 2 each):

- No new test debt: no skipped/todo tests, no snapshots, no duplicated bodies, tests assert visible behaviour, the suite stays lean (prompt asked for it explicitly).
- No unexplained suppressions: no `eslint-disable`, `@ts-ignore`, `@ts-expect-error` or `any` without a stated reason (B10 removes the only one).
- Types sound: `npm run typecheck` passes in strict mode; no casts hiding real errors.
- Follows AGENTS.md: tests next to code, tokens for colors and spacing, explicit-path commits, typecheck, lint, test and build pass.
- Final message notes the decisions: both bug causes, how page names are centralised, rounding rules in the calculator, the useAsync fix, anything vague (key facts chosen for the client page).
