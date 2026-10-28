# Task C: watchlist and notifications, two bugs, a formatting refactor, price alerts and a watchlist page

Fixture: Pulse at `dd7f9b3` (origin2.git `main`). Hidden tests: copy `hidden/*` into `src/__bench__/` and run `npx vitest run src/__bench__`. They mount `src/main.tsx` at a route with the fixture's 120 ms mock latency, so any new provider must be wired in `main.tsx` (or inside `App`). Test names start with the ask id. `regression.test.tsx` passes on the unmodified fixture and must still pass.

Kinds: S = small, M = medium (bug or refactor), L = large, D = docs.

| Id | Kind | Expected outcome | Depends on | Check |
| --- | --- | --- | --- | --- |
| C1 | S (label) | WatchButton text "Add to watchlist" (aria-pressed false) / "On watchlist" (true); star kept, aria-hidden. | none | Hidden C1 |
| C2 | S (icons) | Every notification item shows a kind icon: inline SVG, hidden from assistive tech (`aria-hidden="true"`, `role="presentation"` or `role="none"` on itself or an ancestor), next to the kind label. | none | Hidden C2 |
| C3 | S (label) | Bell header button "Mark all as read" becomes "Mark all read". | none | Hidden C3 |
| C4 | S (colors) | New token `--color-badge`: light `#d92d20`, dark `#ff6b61`; the unread bubble's background uses `var(--color-badge)` instead of `--color-down`. | none | Hidden C4 |
| C5 | S (copy) | Dashboard Watchlist rows show the instrument name under the symbol ("Apple Inc.", "Euro / US dollar", "Gold spot"). | none | Hidden C5 |
| C6 | S (copy) | Settings Email alerts description becomes "When one of your price alerts goes off." | none | Hidden C6 |
| C7 | M (bug 4) | "Mark all read" updates the bell immediately: trigger name becomes "Notifications", no item keeps its "Mark ... as read" button. Cause: the updater mutated items and returned the same array, so React bailed out and the memoised count never recomputed; fix returns new objects/array. | C3 (button label; test accepts both) | Hidden C7; rubric: unit test, cause in final message |
| C8 | M (bug 5) | Sparkline maps the highest value to the smallest y (`height - padding - ...`). AAPL 3M chart ends higher on screen than it starts; TSLA ends lower. Unit test asserts orientation. | none | Hidden C8 (two tests) |
| C9 | M (refactor) | One formatting module holds every money/price/number formatter (`formatPrice`, `formatSignedCurrency`, `formatQuantity`, `formatMultiple`, `formatBasisPoints`, plus the existing `format.ts` ones); arithmetic (`sum`, `toUsd`, `toneOf` ...) may stay separate; all imports updated; the dashboard instruments table uses the shared price formatter: EURUSD "$1.0842", GBPUSD "$1.2967", XAU "$2,641.50". | none | Hidden C9; rubric for the consolidation (no duplicate price formatter left) |
| C10 | L | `/alerts`, sidebar link and top bar "Alerts". Form: "Instrument" select (options "SYMBOL Name"), "Condition" select ("goes above", "goes below"), "Price" number, "Add alert". List items "AAPL goes above $200.00" (instrument's price digits: "EURUSD goes below $1.1000"), badge "Triggered" / "Watching", a "Remove" button. Empty: "No alerts yet." Empty/zero price: "Enter a price above zero", nothing added. Persisted across reload. Each triggered alert yields exactly one unread bell notification titled "AAPL is above $200.00" (bell goes from 3 to 4 unread; untriggered alerts add nothing); reload neither duplicates it nor resets its read state; "Mark all read" clears it. Unit tests. | C7 (mark all read must work), C9 (price digits; formatPrice already gives them) | Hidden C10 (seven tests) |
| C11 | L | `/watchlist`, sidebar link and top bar "Watchlist". Table "Watched instruments": symbol and name, last price ("$227.48", "$1.0842", "$2,641.50"), day change, 1 month Sparkline labelled "SYMBOL 1 month trend", a "Remove" button per row. "Add instrument" select (only unwatched, "SYMBOL Name") with "Add". Empty: "Your watchlist is empty." Row click opens drawer "Instrument details": instrument name heading, key stats (e.g. "Previous close"), the shared WatchButton, link "Open instrument page" (`/instruments/SYMBOL`). Same storage as the dashboard watchlist and WatchButton (adding MSFT here shows MSFT pressed on its page). Unit tests. | C1 (drawer button label), C8 (trend direction) | Hidden C11 (six tests) |
| C12 | D | README covers the alerts page and bell integration, the watchlist page, the formatting module and where alerts/watchlist/read state are stored. | C9, C10, C11 | Rubric only |

Independent: C1 to C9. Chains: C7 -> C10 (mark all read on alert notifications); C1 -> C11 (drawer button label); C8 -> C11 (trend direction); C9 touches nearly every component that imports formatters, so it conflicts textually with C1, C5, C10, C11. Shared files: `NotificationBell.tsx` (C3), `NotificationItem.tsx` (C2, C10), `useNotifications.tsx` (C7, C10), `Sidebar.tsx`/`TopBar.tsx`/`App.tsx` (C10, C11), `theme.css`/`global.css` (C4 and others).

## Source sentences for hidden assertions

- C1: "Make it "Add to watchlist" when it's not on the list and "On watchlist" when it is"
- C2: "each notification should have a little icon for what kind it is ... SVG, decorative, screen readers just hear the label like now"
- C3: ""Mark all as read" is too long for that header, call it "Mark all read""
- C4: "Give it its own token, --color-badge, #d92d20 in light and #ff6b61 in dark, and use that for the bubble"
- C5: "Put the instrument name under the symbol, like Top movers does"
- C6: "Change it to "When one of your price alerts goes off.""
- C7: "when I click "Mark all as read" nothing happens, the count stays at 3 and the items still look unread"
- C8: "the price chart on the instrument page is upside down ... Every chart that goes up looks like it goes down and the other way round"
- C9: "The dashboard instruments table shows EURUSD as $1.08 but the instrument page says $1.0842 ... so a price always has the same digits wherever it shows"
- C10: "New page "Alerts" in the sidebar, at /alerts, top bar says "Alerts"", ""Instrument" dropdown (symbol then name for each option), "Condition" dropdown with "goes above" and "goes below", a "Price" box and an "Add alert" button", "like "AAPL goes above $250.00" ... EURUSD would be like "EURUSD goes below $1.1000"", "a badge, "Triggered" if the current price is already past it, otherwise "Watching", and a "Remove" button", ""No alerts yet."", ""Enter a price above zero"", "They stay after a reload", "an unread notification titled like "AAPL is above $250.00", so the count goes up by one, and it should only ever be there once, a reload must not add it again", "Mark all read has to clear those too"
- C11: "Sidebar link "Watchlist", /watchlist, top bar "Watchlist". A table called "Watched instruments"", "last price, day change, and a little 1 month trend line, the small sparkline, labelled like "AAPL 1 month trend"", "an "Add instrument" dropdown with only the instruments that aren't already on the list, symbol then name again, and an "Add" button", "a "Remove" button", ""Your watchlist is empty."", "a drawer called "Instrument details" with the instrument name as its title, the key stats ..., the same watch button, and a link "Open instrument page"", "if I add something here the instrument page shows it as on the watchlist"

## Not checked by hidden tests

Icon artwork (C2), whether C9 left a second price formatter or stale imports (rubric reads the diff), what happens to an alert's notification after the alert is removed (engineer's call, should be noted), sync between two watch controls on one screen, unit tests, README (C12), and `npm run typecheck`, `lint`, `test`, `build`.
