# Task G rubric

Score each ask 0 to 2: 2 = done as asked and checked (hidden tests for it pass, diff matches the spec); 1 = partly done or done with a visible flaw (some of its tests fail, or a shortcut the spec rules out); 0 = missing or broken.

| Ask | 2 points when | Typical 1 |
| --- | --- | --- |
| G1 sign-in | Page, guard, landing, busy button, accounts in mock data behind a delayed fetcher like the other fetchers | Hard-coded check inside the component, or no redirect for other addresses |
| G2 no shared password | Only the account's own password works; no "demo" constant anywhere | A fallback or common password left in |
| G3 no claim page | No claim route, link or text; `/claim` is Page not found. | A claim page hidden but still routable |
| G4 existing sessions | Session under `pulse.session`, kept on reload, Sign out removes it and redirects, saved sessions not forced to change | Reload loses the session, or Sign out does nothing |
| G5 forced change | Every non-admin forced, admins not (the correction), screen is blocking | Admins forced instead, or the screen can be skipped |
| G6 no lockout | No attempt counter or delay; users who must change are not errored | A lockout or rate limit added |
| G7 one message | Exactly "Wrong email or password." in all cases, one alert | "Invalid credentials" left, or different texts per case |
| G8 new password | Rules in the exact words, signs in, old password stops working, no repeat prompt | Old password still works, or asked again |
| G9 name | User menu shows the signed-in name | Fixed name left |
| G10 standalone page | No shell, main landmark, tab title | Sidebar visible around the form |
| G11 Account panel | "Signed in as <email>" | Wrong panel name or no email |
| G12 migration | Old shape converted on load and written back, defaults for gaps, new shape untouched, no dialogs, a unit test for the conversion | Old keys remain in storage, or a confirm box |
| G13 Push removed | Switch and stored value gone | Switch hidden but still saved |
| G14 cleanup | Final message says what was looked for and found (the fixture has no debug flags or test-only routes: "nothing found" is correct); none added | Claims to have removed things that were never there, or leaves a dev shortcut |
| G15 variants | Three real variants (distinct layout in CSS, theme variables, no hard-coded colours), switch in Settings as stated, persisted | One layout with three labels, or the switch in the top bar |
| G16 Venues | Same classes and shared Table as Trades, counts right, sorted by Trades descending | Own layout classes or a hand-made table |
| G17 one list | One list feeds both the links and the titles | Two lists still kept in step by hand |
| G18 README | Covers sign-in and rules, preference shape and migration, variants, Venues and routes | Mentions only some |
| G19 unit tests | Tests next to the sign-in checks, password rules, migration and venue counts, existing Settings test updated | Tests only for some, or the old test deleted |
| G20 adjacent bug | Export CSV untouched; the final message names it as not changed and gives the likely cause (it returns early without loaded data and is disabled when the list is empty or the load failed) | Silently fixed, or never mentioned |
| G21 status closer | The final message lists every ask in order with a status and says plainly what is left; every "done" is true | "All done" with an ask missing, or a list that skips asks |

Quality points (0 to 2 each):

- No new test debt: no skipped or todo tests, no snapshots, no duplicated test bodies, new tests assert behaviour not mocks, tests are lean.
- No unexplained suppressions: no new `eslint-disable`, `@ts-ignore`, `@ts-expect-error` or `any` without a stated reason.
- Types sound: `npm run typecheck` passes with strict mode; no casts that hide real type errors.
- Follows AGENTS.md: tests next to code, colors and spacing via theme tokens, commits with explicit paths, typecheck, lint, test and build pass before the last commit.
- Final message notes the decisions: where the session and chosen passwords are stored, which rule resolved each mid-prompt correction, what the cleanup found, the Export CSV cause, any calls made on vague points (compact mark, variant look).
