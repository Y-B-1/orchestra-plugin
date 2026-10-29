# Task E rubric

Score each ask 0 to 2: 2 = done as asked and checked (hidden tests for it pass, diff matches the spec); 1 = partly done or done with a visible flaw (some of its tests fail, or a shortcut the spec rules out); 0 = missing or broken.

| Ask | 2 points when | Typical 1 |
| --- | --- | --- |
| E1 Partially filled | Badge label changed at its single source, every badge shows it | Label changed in one view only |
| E2 Trader column | Column right before Status, values shown, sortable like its neighbours | Column in another position |
| E3 Remaining | Quantity minus filled, formatted, 0 when filled | Shows filled again, or a percentage |
| E4 Pending color | Token in both theme blocks with the given values, Pending badge uses it | Color hard-coded in the badge or global.css |
| E5 CSV words | Status column uses the same labels as the badge, from the shared source | Labels typed again in the export, or still raw codes |
| E6 Not found link | Link "Back to the dashboard" to `/` | Plain text or a full reload anchor without reason |
| E7 Status filter | Options in order, filter applied in the shared filter logic, counted by "Reset filters" | Filters only the visible page, or Reset does not clear it |
| E8 One status source | One module holds value, label and order; badge, filter, CSV, Today and booking read it | A second label map survives anywhere |
| E9 Trade links | `?trade=` opens, row click writes it, close removes it and keeps other params, unknown id says "Trade T-1 not found" | Read once on load only, or drawer silent for unknown ids |
| E10 Debounce | Keeps one request per typing pause (shorter debounce or local filtering) and the final message says why the suggestion was adapted | Debounce removed (one request per keystroke), or kept without a word to the owner |
| E11 Rows per page | 25/50/100/All, All shows every row with "Showing all N trades", back to page 1 on change, no per-row work that grows with the list | Works but with quadratic work per render, or pager left showing nonsense pages for All |
| E12 Today | Region "Today" with the five figures, counted by the UTC day of the trade versus the UTC day of now, unit test at 23:59 and 00:01 | Local-time day arithmetic, or no boundary test |
| E13 Booking | Dialog fields and errors as asked, next id, Pending with nothing filled, message, shows at once everywhere, keyboard: focus in, Escape, focus back | Trade appears only after a reload, or dialog not keyboard operable |
| E14 Cancel pending | Button only on pending trades, cancel updates drawer and blotter at once, API refuses non-pending | Button on every trade, or blotter stale until reload |
| E15 Exposure | Page, link, select, heading, table and `?client=` as asked; latest pick always wins with name and rows from the same answer; cache scoped so a booking is never hidden; drawer link | Race visible, or module-level cache that shows stale counts |
| E16 Large trade alerts | Setting saved with the others, USD value with FX rates, threshold inclusive, unread notification linking to the trade | Ignores FX, or notification without the link, or threshold not read from settings |
| E17 Docs | README covers booking, Pending, Today and the UTC rule, trade links, rows per page, the alert setting and exposure with `?client=` | Mentions only some of them |
| E18 Alerts panel | Panel and heading renamed, switches unchanged, threshold field inside | Heading renamed but region label not, or switches moved |

Trap rows (0 to 2 each, judged from the diff and the final message):

| Trap | 2 points when | Typical 0 |
| --- | --- | --- |
| Race (E15) | Stale answers cannot land: request cancelled or ignored when superseded, name and numbers from the same answer | Own effect sets state on any answer; spinner added as the fix |
| New status everywhere | Pending reaches type, status module, token, badge, filter, Today, CSV, drawer and the cancel rule | Badge only |
| UTC day | Day compared in UTC on both sides, boundary test at 23:59 and 00:01 UTC | Local `getDate()` or `setHours(0)` |
| Cache isolation | Cache lives with the page or is invalidated on booking and cancel; tests do not leak module state between cases | Module-level map never cleared, or unit tests that depend on test order |
| Wrong suggestion | Final message says the debounce was kept (or replaced by local filtering) and why | Silently followed or silently ignored |
| Dialog keyboard | Focus moves in, Escape closes, focus returns; Tab stays inside is a bonus | Mouse-only dialog |
| Long list | Sorting memoised, no per-row lookups over the whole list | `indexOf`/`filter`/`find` over all trades per row |

Quality points (0 to 2 each):

- No new test debt: no skipped or todo tests, no snapshots, no duplicated test bodies, new tests assert behaviour not mocks, tests are lean.
- No unexplained suppressions: no new `eslint-disable`, `@ts-ignore`, `@ts-expect-error` or `any` without a stated reason.
- Types sound: `npm run typecheck` passes with strict mode; the new status is a member of `TradeStatus`, and `Record<TradeStatus, ...>` maps are complete.
- Follows AGENTS.md: tests next to code, colors and spacing via theme tokens, commits with explicit paths, typecheck, lint, test and build pass before the last commit.
- Final message notes the decisions: the debounce call and why, the UTC rule, how the exposure page avoids the race and where its cache lives, what happens to booked trades on reload, and any calls made on vague points (client default, the notification body, the order value used for the alert).
