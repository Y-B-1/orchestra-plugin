# Task D: portfolio, clients and reports week, a misleading bug, a settings migration, safe note formatting, currencies and a book panel

Fixture: Pulse at `dd7f9b3` (origin2.git `main`). Hidden tests: copy `hidden/*` into `src/__bench__/` of the finished branch and run `npx vitest run src/__bench__`. They mount the real entry `src/main.tsx` at a route (see `hidden/helpers.tsx`), with the fixture's 120 ms mock latency; `resetApp` clears localStorage after each test and `seed` writes a raw saved value before mounting. Test names start with the ask id. `regression.test.tsx` passes on the unmodified fixture and must still pass.

Kinds: S = small, M = medium (bug, migration or feature slice), L = large (new capability), D = docs.

| Id | Kind | Expected outcome | Depends on | Check |
| --- | --- | --- | --- | --- |
| D1 | S (sign) | Portfolio summary cards "Unrealized P&L" and "Day change" show a "+" on gains: "+$2.2M", "+$121.6K"; losses keep "-"; "Market value" ($31.2M) and "Cost basis" get no sign. | none (D14 changes the currency of the same cards) | Hidden D1 |
| D2 | S (legend) | Allocation legend items read "Equities: $11.9M (38.0%)", "FX: $8.4M (27.0%)", "Commodities: $4.2M (13.6%)". | none | Hidden D2 |
| D3 | S (format) | Client drawer "Assets under management" in whole dollars: "$1,250,000,000" for Northwind, no ".00". Cents stay everywhere else (holdings, trade fees, notionals). | none; trap 6 | Hidden D3; regression tests for cents elsewhere |
| D4 | S (order) | Client list ordered by AUM, biggest first. **Superseded by D15**; tests expect D15. | conflicts with D15 | Rubric (trap 2) |
| D5 | S (copy) | Clients search placeholder "Search by name, contact or region"; accessible name stays "Search clients". | none | Hidden D5 |
| D6 | S (copy) | Report meta line "Oct 27, 2026 · A. Moreau · 6 pages"; without pages "Oct 25, 2026 · L. Duarte". | none | Hidden D6 D7 |
| D7 | S (copy) | Scheduled reports read "Due Oct 30, 2026 · L. Duarte" and "Due Oct 31, 2026 · J. Ortiz". | D6 (same line) | Hidden D6 D7 |
| D8 | M (bug) | Notional of a cancelled trade reads "$0.00" (no "0.0000" anywhere) in the trade drawer, the trade blotter and the dashboard's "Latest trades". Root cause: notionals are formatted with `formatPrice`, whose `priceDigits` picks 4 decimals for any value under 2 (meant for FX quotes), so a zero notional gets four decimals. The shared Notional column (`tradeColumns.tsx`, used by the blotter and the dashboard) and the drawer must both format the notional as an amount. Regression unit test that fails before the fix. | none; trap 1 | Hidden D8 (two tests, three surfaces); rubric for cause and test |
| D9 | M | Portfolio "Book" select, "All books" default then each book. Picking Growth shows only NVDA and TSLA; totals row "Total (2 positions)", $5,398,600.00, +$1,168,100, weight 17.3% (share of the whole portfolio). Cards stay whole-portfolio. Back to "All books" restores 11 positions. | none (D14 and D17 read the filtered rows) | Hidden D9 |
| D10 | M (migration) | Settings "Weekly digest" switch replaced by a "Report digest" select with "Off", "Daily", "Weekly" (default Weekly). Old saves `{weeklyDigest: false}` read as "Off", `true` as "Weekly"; theme and switches keep their saved values; a new choice persists across a reload. Unreadable saves (`{oops`, `null`, `[1,2]`, `"dark"`, wrong field types) fall back to defaults without a crash. | none; trap 3 | Hidden D10 (three tests); rubric for a migration unit test |
| D11 | M | "Search reports" box filters the current tab by title or author, case-insensitive, stays applied across tabs; "No reports match your search." when the tab has reports but none match. | D6 (same list) | Hidden D11 |
| D12 | M (security) | Client notes render `**bold**` as bold and `[label](https://...)` as a link. Raw HTML in a note is shown as text: no `img` element, no handler runs; a `javascript:` link never becomes an `href`. | none; trap 4 | Hidden D12; rubric: no `dangerouslySetInnerHTML` on note text, or a sanitiser that whitelists |
| D13 | M | "Pin" / "Unpin" button per note; pinned notes first with a "Pinned" label; pins persist. Notes saved in the old shape (no pinned flag) still show, unpinned, and can be pinned. An unreadable saved notes value shows "No notes yet." and still accepts new notes. | D12 (same list); trap 3 | Hidden D13 (two tests) |
| D14 | L | "Show values in" select with USD (default), EUR, GBP. Converts at today's rates (`fetchFxRates`, USD per unit, so divide): cards (EUR: Market value "€28.8M", Unrealized P&L "+€2M", Day change "+€112.2K"; GBP: "£24.1M"), holdings market value and P&L columns (AAPL "€2,517,764.25"), header "Market value (EUR)", totals row "€28,786,217.91", allocation legend "Equities: €10.9M (38.0%)", the D16 panel, the holdings hint and the Cost basis note. Prices and average cost stay in the instrument currency (AAPL "$227.48"). | D1, D2, D16 | Hidden D14 (two tests) |
| D15 | S (order) | Client list A to Z by name: Baltic Shipping Fund first, Sable Insurance last. Supersedes D4. | D4; trap 2 | Hidden D15; rubric names the conflict |
| D16 | L | Panel "P&L by book" with a table named "P&L by book": columns Book, Positions, Market value, Unrealized P&L; rows Macro overlay, Rates, Core equity, Growth, Real assets (market value descending); whole units ("$6,464,538", "+$797,864", "-$73,661"); ignores the Book filter, follows the currency (Core equity "+€735,901"). | D14 | Hidden D16 (two tests) |
| D17 | M (open) | Visible control named exactly "Export holdings". Either shape passes: a file download (CSV or similar, via `URL.createObjectURL`) or a print view (`window.print` or a print route). Should export the rows and currency on screen. | D9, D14; trap 7 | Hidden D17; rubric: final message states the shape and why |
| D18 | D | README covers the book filter, currencies, P&L by book, export, note formatting and pins, report search, the digest setting and the other visible changes. | all | Rubric only |

Independent: D1 to D3, D5 to D8, D10 to D13, D15. Dependencies: D14 touches the same cards, table, totals row and legend as D1, D2 and D9; D16 and D17 read D14's currency; D17 reads D9's filter; D4 and D15 set the same default; D12 and D13 both edit the notes list.

Files touched by a reference solution: `utils/format.ts` (options on `formatCurrency` and `formatCompactCurrency`), `utils/portfolio.ts` (book grouping, `fromUsd`), new `utils/settings.ts` (migration), new `utils/noteText.ts` (parser, no HTML), `components/trades/tradeColumns.tsx` and `TradeDetail.tsx`, portfolio components split into `PortfolioControls`, `BookPnl`, `money.ts`, `exportHoldings.ts`, `HoldingsTable`, `PortfolioSummary`, `AllocationChart`; `ClientNotes`, new `NoteText`, `storedNotes.ts`; `ClientDrawer`, `pages/Clients.tsx`, `pages/Reports.tsx` with `components/reports/reportMeta.ts`, `pages/Settings.tsx`, `hooks/useSettings.tsx`, `types.ts`, `global.css`, README, plus unit tests. Largest changed source file in the reference: `types.ts` at 173 lines; `pages/Portfolio.tsx` is 95 lines.

## Source sentences for hidden assertions

- D1: "Put a plus in front when it's up, so Day change reads "+$121.6K" and Unrealized P&L "+$2.2M" ... Market value and Cost basis ... no plus"
- D2: "so "Equities: $11.9M (38.0%)", same one decimal as the bars"
- D3: "Whole dollars there, "$1,250,000,000". Only there though"
- D5: "Make the placeholder "Search by name, contact or region" ... Screen readers can keep hearing "Search clients""
- D6, D7: "so "Oct 27, 2026 · A. Moreau · 6 pages", and when there are no pages it's just "Oct 25, 2026 · L. Duarte"", ""Due Oct 30, 2026 · L. Duarte". Same for the month-end one, "Due Oct 31, 2026 · J. Ortiz""
- D8: "show the notional as "$0.0000" ... it should just read "$0.00" like any other amount"
- D9: "a "Book" dropdown ... first option "All books" ... for Growth it says "Total (2 positions)" with $5,398,600.00 ... Growth is 17.3%"
- D10: "a "Report digest" dropdown with "Off", "Daily" and "Weekly", Weekly being the default ... whoever turned the weekly digest off must still have it off ... if something saved can't be read just fall back to the defaults"
- D11: ""Search reports" for screen readers ... by title or author, case doesn't matter ... It stays applied when you switch tabs ... "No reports match your search.""
- D12: "**bold** with two stars ... [the pack](https://example.com/pack) ... People paste all sorts of things out of emails into those notes"
- D13: "a "Pin" button, a pinned note goes to the top of the list with a little "Pinned" label and its button says "Unpin" ... still there after a reload ... those must all still show up exactly as before, just unpinned"
- D14: ""Show values in" dropdown ... "USD", "EUR" and "GBP" ... Market value becomes "€28.8M" ... "Market value (EUR)" ... AAPL is still $227.48"
- D15: "forget what I said about AUM order earlier ... alphabetical, A to Z by name"
- D16: "called "P&L by book", with a table also called "P&L by book" ... "Book", "Positions" ... "Market value" and "Unrealized P&L", biggest market value first. Whole units only ... Core equity reads 3 positions, $6,464,538 and +$797,864 ... doesn't care what the Book dropdown is set to, but it does follow "Show values in""
- D17: "an "Export holdings" button ... whatever you think works best"

## Traps

**Trap 1, misleading bug report (D8).** The owner blames the trade drawer ("doing its own maths for cancelled trades"). The maths is right (notional = filled quantity × price = 0); the defect is formatting: notionals go through `formatPrice`, whose `priceDigits` gives 4 decimals to anything under 2, so 0 reads "$0.0000". The same formatter feeds the shared Notional column used by the blotter and the dashboard's Latest trades. A correct solution formats notional as an amount in one shared place used by the column and the drawer (or fixes the helper for amounts), adds a unit test that fails before the fix, and explains the cause. A typical wrong one special-cases cancelled trades in `TradeDetail.tsx` and fails the blotter and dashboard checks.

**Trap 2, conflicting asks (D4 then D15).** Early: client list by AUM, biggest first. Later, casually inside the currency ask: "forget what I said about AUM order earlier ... alphabetical". Tests expect A to Z. Credit needs the final message to name the conflict and say the later ask won. A typical wrong solution implements AUM order and stops reading, or implements both orders in sequence and leaves AUM.

**Trap 3, saved-data migration (D10, D13).** `pulse.settings` already holds `{theme, emailAlerts, pushAlerts, weeklyDigest}`. A correct solution migrates `weeklyDigest` to the new digest (false → Off, true → Weekly), validates each field and falls back to defaults on anything unreadable (bad JSON, `null`, arrays, strings, wrong types), with a unit test. Typical wrong ones: read only the new field so every old user lands on "Weekly" (the user who turned it off gets emails again); or spread the raw value over defaults and crash or show garbage on `null`/arrays/wrong types; or keep both fields. For notes, the old array without a pinned flag must still load, and a non-array value must not blank the app (the fixture's `notes.map` crashes on `{"x":1}`).

**Trap 4, unsafe rich text (D12).** A correct solution parses `**bold**` and `[label](url)` into React elements, renders everything else as text, and only lets `http:`/`https:` URLs become hrefs. Typical wrong ones: regex-replace into an HTML string and use `dangerouslySetInnerHTML` (the `<img onerror>` mounts), or accept any URL in the link syntax (a `javascript:` href).

**Trap 5, file budget (D1, D2, D9, D14, D16, D17).** Six asks land on the portfolio page. A correct solution splits it into parts (controls, book panel, export helper, currency helper) and keeps every changed source file under 500 lines. A typical wrong one grows `pages/Portfolio.tsx` or `HoldingsTable.tsx` into one large component. Rubric only; the scorer records the largest changed file.

**Trap 6, shared API contract (D3, D1, D14).** Whole-dollar AUM and signed compact amounts tempt a change to `formatCurrency` / `formatCompactCurrency`, which the dashboard KPIs, holdings, trade drawer fees, instrument key stats and the allocation legend all use. A correct solution adds an opt-in option (or a new helper) and leaves default output unchanged. A typical wrong one drops cents or adds signs globally; the regression file checks "$48.2B" with no sign on the dashboard, "$2,729,760.00" and "+$468,960" in holdings, "$2.10" fees and "$7,039,565.00" notional on trades, "€214.90" and "$3.5T" on instrument pages.

**Trap 7, two valid shapes (D17).** "Export holdings" may be a CSV download or a print view; the test accepts either through the exact control name. Credit needs the final message to state the shape and the reason (for example: CSV because the risk team re-reads it in their own tools, and it reuses the existing CSV helper).

## Not checked by hidden tests

Unit tests added by the engineer, the cause explanation for D8, the D4/D15 decision in the final message, the D17 shape rationale, file sizes (trap 5), README (D18), and whether `npm run typecheck`, `lint`, `test`, `build` pass (run them).
