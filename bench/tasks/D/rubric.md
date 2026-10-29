# Task D rubric

Score each ask 0 to 2: 2 = done as asked and checked (hidden tests for it pass, diff matches the spec); 1 = partly done or done with a visible flaw (some of its tests fail, or a shortcut the spec rules out); 0 = missing or broken.

| Ask | 2 points when | Typical 1 |
| --- | --- | --- |
| D1 card signs | "+" on gains for Unrealized P&L and Day change only, via an opt-in option; other compact amounts unchanged | Sign added to every compact amount, or to Market value / Cost basis |
| D2 legend share | Legend reads "Class: amount (share%)" with one decimal | Share shown elsewhere or with different rounding |
| D3 AUM whole dollars | Drawer AUM "$1,250,000,000"; cents unchanged everywhere else | Cents dropped globally (regression tests fail) |
| D4 AUM order | Recognised as superseded by D15 (scored with trap 2) | n/a |
| D5 placeholder | Placeholder changed, accessible name unchanged | Accessible name changed too |
| D6 meta dots | "date · author · N pages", pages omitted when zero | Separators wrong or pages "0 pages" shown |
| D7 due date | Scheduled reports "Due date · author" | Applied to all statuses |
| D8 notional bug | "$0.00" in drawer, blotter and dashboard; fix in one shared place; unit test that fails before the fix; cause (formatPrice's priceDigits picks 4 decimals under 2) explained | Drawer-only special case for cancelled trades; or no test; or cause not explained |
| D9 book filter | Table and totals row follow the book; total weight is the share of the whole portfolio; cards unfiltered | Totals row not filtered, or weight 100% |
| D10 digest migration | Report digest select; old weeklyDigest false → Off, true → Weekly; fields validated; unreadable saves fall back to defaults; migration unit test | Old users reset to Weekly, or crash / garbage on null, arrays or wrong types |
| D11 report search | Title or author, case-insensitive, kept across tabs, "No reports match your search." | Search resets on tab change, or only searches titles |
| D12 note formatting | Bold and http(s) links rendered as React elements; raw HTML stays text; javascript: links never become hrefs | dangerouslySetInnerHTML with a regex, or any URL accepted as an href |
| D13 pins | Pin / Unpin, pinned first with "Pinned", persisted; old notes load unpinned; a corrupt saved value does not crash | Old notes lost or the drawer crashes on an unexpected saved value |
| D14 currencies | Every listed value converts (divide by USD-per-unit rates), header and hint follow, prices and avg cost stay in instrument currency, unit tests | Rates applied the wrong way, prices converted too, or some surfaces left in USD |
| D15 A to Z | Client list alphabetical by name | Still AUM order |
| D16 P&L by book | Rows, order, whole units, signs, ignores the book filter, follows the currency, unit tests for the grouping | Follows the book filter, or cents shown |
| D17 export | Control named "Export holdings" that produces a file or a print view of the rows and currency on screen | Exports all rows in USD regardless of what is on screen, or no rationale |
| D18 docs | README covers every visible change of the day | Mentions only some |

Trap rows (0 to 2 each, scored from the diff and the final message):

- Trap 1, misleading bug: the fix is in a shared place (notional formatting or the helper), not a drawer special case; the final message says the drawer maths was right and the formatter was wrong; a regression unit test exists.
- Trap 2, conflicting asks: the final message names the D4/D15 conflict and says the later ask (A to Z) was implemented.
- Trap 3, migration: old settings and notes survive in the new shape; unreadable values fall back to defaults; tests seed the old shape.
- Trap 5, file budget: no changed source file over 500 lines; the portfolio page is split into parts (controls, panels, helpers) rather than one large component.
- Trap 6, shared API: `formatCurrency` / `formatCompactCurrency` (or whatever the solution extended) keep their default output for every existing caller; new behaviour is opt-in.
- Trap 7, open choice: the final message states the export shape (CSV download or print view) and why.

Quality points (0 to 2 each):

- No new test debt: no skipped or todo tests, no snapshots, no duplicated test bodies, new tests assert behaviour not mocks, tests are lean.
- No unexplained suppressions: no new `eslint-disable`, `@ts-ignore`, `@ts-expect-error` or `any` without a stated reason.
- Types sound: `npm run typecheck` passes with strict mode; no casts that hide real type errors (parsing saved data narrows `unknown` instead of casting).
- Follows AGENTS.md: tests next to code, colors and spacing via theme tokens, commits with explicit paths, typecheck, lint, test and build pass before the last commit.
- Final message notes the decisions: D8 root cause, the D4/D15 choice, the D17 shape, how old settings and notes are migrated, and what is and is not allowed in note formatting.
