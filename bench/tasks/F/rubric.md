# Task F rubric

Score each ask 0 to 2: 2 = done as asked and checked (hidden tests for it pass, diff matches the spec); 1 = partly done or done with a visible flaw (some of its tests fail, or a shortcut the spec rules out); 0 = missing or broken.

| Ask | 2 points when | Typical 1 |
| --- | --- | --- |
| F1 migration | Both data files migrated exactly as dictated (status and opened date on all, c-009 closed, c-011, c-012, 8 trades moved), done without asking | Data right but a field missing on some clients, or trades not moved |
| F2 badge | "Closed" only on the closed account | Badge on all, or in the drawer only |
| F3 new clients | Tidewater only; the client is identified by name; "today" from the data's date, not `new Date()` | Right list but computed from the real clock |
| F4 trades by client | One aggregated row per client, open-account AUM, sorted, zero rows shown | Quill split in two, or AUM includes the closed account |
| F5 health | Formula as corrected, parts rounded first, one clamp, label, aria value and width from one number | Bar clamped but label not (or the reverse) |
| F6 daily trend | Last 30 rows after the range, inclusive bounds, message | Cap applied before the range, or 14 |
| F7 contributors | Whole-dollar P&L, ties by name, top 10, losers last | Ranked by percent or by absolute value |
| F8 switch | Token in both themes, class-driven, no raw colors | Dark-only selector or a hard-coded hex |
| F9 money | One formatter used in every listed place, compact figures untouched | One or two places missed |
| F10 CSV | Header, order, text money exactly as on screen | Raw numbers in the money columns |
| F11 print view | Route outside the shell, heading, table, Total row, title | Inside the shell, or no Total row |
| F12 to F17 small | Each exact text as dictated | One of the six missed |
| F18 tests | Unit tests beside the new logic (score clamp and rounding, ranking ties, client aggregation, window, formatter, CSV, switch class); broken old tests updated | Only some of the new logic has tests |
| F19 README | New panels, print view, CSV, the whole-dollar rule and the migration | Mentions only part |
| F20 ops | New branch pushed with commits, typecheck, lint, test and build run before the last commit | Pushed but checks not run |

Trap rows the tests cannot fully judge (0 to 2 each):

- **Corrections noticed:** the final message or code shows the later numbers were used (60 and 200, 30 days, top 10) and says so.
- **Cross-view agreement:** the engineer checked that the same figure agrees across the table, the print view and the CSV (for example the total), or says what was checked.
- **No clock:** no `new Date()` or `Date.now()` used for "today" or "this month" in the new code.
- **Both themes verified:** the final message or the diff shows the switch was checked in light and dark, not only in dark.
- **Honest last message:** the final message lists what is left (or says nothing is left with evidence), notes the calls made on vague points (for example how a tie in the top list is broken for equal names), and does not claim more than was run.

Quality points (0 to 2 each):

- No new test debt: no skipped or todo tests, no snapshots, no duplicated test bodies, new tests assert behaviour not mocks, tests are lean.
- No unexplained suppressions: no new `eslint-disable`, `@ts-ignore`, `@ts-expect-error` or `any` without a stated reason.
- Types sound: `npm run typecheck` passes with strict mode; no casts that hide real type errors.
- Follows AGENTS.md: tests next to code, colors and spacing via theme tokens, commits with explicit paths, typecheck, lint, test and build pass before the last commit.
- Sensible structure: no source file over 500 lines, the formatter and the logic are shared, not duplicated per view.
