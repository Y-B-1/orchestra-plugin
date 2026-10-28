# Task C rubric

Score each ask 0 to 2: 2 = done as asked and checked (its hidden tests pass, diff matches the spec); 1 = partly done or done with a visible flaw; 0 = missing or broken.

| Ask | 2 points when | Typical 1 |
| --- | --- | --- |
| C1 watch label | New labels, aria-pressed kept, star kept | Labels changed but pressed state lost |
| C2 kind icons | One aria-hidden SVG per kind, label unchanged | Icons readable by screen readers, or only some kinds |
| C3 Mark all read | Label changed | |
| C4 badge token | Token in both themes in theme.css, bubble uses it | Color hard-coded in global.css |
| C5 names | Name under symbol in dashboard watchlist, layout intact | Layout broken |
| C6 copy | Text changed | |
| C7 mark-all bug | Immutable update, count updates at once, unit test, cause explained | Forced re-render or a reload hack |
| C8 sparkline bug | y inverted in `sparklinePoints`, unit test for orientation | Flipped with a CSS transform or by reversing the data |
| C9 formatting | One module for all formatters, imports updated, dashboard prices use the shared price formatter | Only InstrumentTable changed, two modules left |
| C10 alerts | Form, list, badges, validation, persistence, exactly-once bell notification with stable read state, mark all read clears it, unit tests | Notification duplicated on reload or not counted |
| C11 watchlist page | Table, trends, add/remove, empty state, drawer with shared WatchButton, shared storage, unit tests | Own storage key, or drawer without the shared button |
| C12 docs | README covers alerts, bell integration, watchlist page, formatting module, storage keys | Partial |

Quality points (0 to 2 each):

- No new test debt: no skipped/todo tests, no snapshots, no duplicated bodies, tests assert visible behaviour and stay lean.
- No unexplained suppressions: no new `eslint-disable`, `@ts-ignore`, `@ts-expect-error` or `any` without a stated reason.
- Types sound: `npm run typecheck` passes in strict mode.
- Follows AGENTS.md: tests next to code, tokens for colors and spacing, explicit-path commits, typecheck, lint, test and build pass.
- Final message notes the decisions: both bug causes, where alerts live, how alert notifications avoid duplicates and keep read state, what happens to a removed alert's notification, how the formatting modules were split.
