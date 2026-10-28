# Task A rubric

Score each ask 0 to 2: 2 = done as asked and checked (hidden tests for it pass, diff matches the spec); 1 = partly done or done with a visible flaw (some of its tests fail, or a shortcut the spec rules out); 0 = missing or broken.

| Ask | 2 points when | Typical 1 |
| --- | --- | --- |
| A1 icons | Every sidebar link, including Compare, has an aria-hidden SVG using currentColor; names unchanged | Icons not hidden from screen readers, or missing on the new link |
| A2 arrows | ▲/▼ in PriceChange, none when flat, all PriceChange users get it | Arrows added in some places only, or arrow on flat values |
| A3 Venue | Column after Client, values shown | Column elsewhere |
| A4 UTC | " UTC" appended, sort not broken by the new text | Suffix outside the Time column or breaks sorting |
| A5 colors | Four token values set in theme.css only | Values hard-coded in components or global.css |
| A6 Clear filters | Renamed, behaviour unchanged | Behaviour changed |
| A7 date bug | End day included via the bound (next midnight, exclusive), unit test added, cause explained | Symptom patched in the page or with string compares that break on time zones; no test |
| A8 sort bug | sortValue uses ISO or epoch, unit test, cause explained | Fixed only for the blotter, or sorts by string of another format |
| A9 refactor | InstrumentTable uses shared Table, custom sort code deleted, initial sort Instrument asc with arrow | Arrow added by hand while keeping a second sort implementation |
| A10 compare | All rows correct, URL round-trip, same-symbol message, link from instrument page, unit tests for the new logic | Works but URL not updated, or values from the wrong source, or no tests |
| A11 search | Groups, links, client drawer opens via the Clients page, Enter/Escape, clears after pick, tests | Missing keyboard handling or client drawer not opened |
| A12 docs | README covers Compare (route and params), search, and the visible changes | Mentions only one of them |

Quality points (0 to 2 each):

- No new test debt: no skipped or todo tests, no snapshots, no duplicated test bodies, new tests assert behaviour not mocks, tests are lean.
- No unexplained suppressions: no new `eslint-disable`, `@ts-ignore`, `@ts-expect-error` or `any` without a stated reason.
- Types sound: `npm run typecheck` passes with strict mode; no casts that hide real type errors.
- Follows AGENTS.md: tests next to code, colors and spacing via theme tokens, commits with explicit paths, typecheck, lint, test and build pass before the last commit.
- Final message notes the decisions: root causes of both bugs, where search sources come from, how the compare page reads the URL, any calls made on vague points (icon set, result limit).
