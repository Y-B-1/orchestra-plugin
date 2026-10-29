# Task G: finish the whole flow (sign-in with six rules, navbar variants, Venues page, preference migration, cleanup)

Fixture: Pulse at `dd7f9b3` (origin2.git `main`). Hidden tests: copy `hidden/*` into `src/__bench__/` of the finished branch and run `npx vitest run src/__bench__`. They mount the real entry `src/main.tsx` at a route (see `hidden/helpers.tsx`), with the fixture's 120 ms mock latency. Test names start with the ask id. `regression.test.tsx` passes on the unmodified fixture and must still pass. It seeds a session under the key the prompt names (`pulse.session`), which the unmodified app ignores.

Kinds: S = small, M = medium, L = large, D = docs, R = report (a message, not a code change).

| Id | Kind | Expected outcome | Depends on | Check |
| --- | --- | --- | --- | --- |
| G1 | L (sign-in) | `/sign-in` with heading "Sign in", fields "Email" and "Password" (type password), button "Sign in". Signed-out visitors to any other address land on `/sign-in`; success lands on the dashboard. Button reads "Signing in..." and is disabled while the request runs; form submit (Enter) works. Accounts in mock data behind a delayed fetcher: dana and owen (admin), marc (trader), ines (analyst), with the passwords in the prompt. | none | Hidden G1 (two tests) |
| G2 | M (rule 1) | No shared or demo password: "demo", a made-up password, or another account's password never signs anyone in. | G1 | Hidden G2 |
| G3 | S (rule 2) | No claim page or link: `/claim` is "Page not found." for a signed-in user; no link or text mentioning "claim" on the sign-in page, the user menu or the page. | G1 | Hidden G3 |
| G4 | M (rule 3) | An existing `pulse.session` (JSON string email) keeps the person signed in and does not trigger the password screen. Sign-in stores the session under that key; a reload keeps the user in; "Sign out" removes the key and goes to `/sign-in`. | G1 | Hidden G4 (three tests) |
| G5 | M (rule 4, with correction) | Every user except admins (marc, ines) see "Choose a new password" (fields "New password", "Confirm new password", button "Save password") after a correct sign-in, and nothing else is reachable. Admins (dana, owen) go straight to the dashboard. The prompt first says admins, then corrects to "every user except the admins": the correction wins. | G1 | Hidden G5 (two tests) |
| G6 | M (rule 5) | Lock no one out: six wrong attempts never block the right password; a user who must change signs in with the current password and gets no "expired/locked" error. | G1, G5 | Hidden G6 (two tests) |
| G7 | S (rule 6, with correction) | Exactly one message, "Wrong email or password.", for an unknown email, a wrong password and "demo"; one alert only. The prompt first says "Invalid credentials" and then corrects it. | G1 | Hidden G7 |
| G8 | M (new password) | At least 10 characters ("Use at least 10 characters.") then matching ("Passwords do not match."). Saving signs the user in on the dashboard; the new password works from then on, the old one fails, and no second prompt. | G5 | Hidden G8 (two tests) |
| G9 | S | The user menu shows the signed-in user's name (not a fixed name). | G1 | Hidden G9 |
| G10 | S | Sign-in page has no sidebar and no top bar, still has a `main`, and tab title "Sign in \| Pulse". | G1 | Hidden G10 |
| G11 | S | Settings has an "Account" panel saying "Signed in as <email>". | G1 | Hidden G11 |
| G12 | L (migration, approved up front) | Stored `pulse.settings` in the old flat shape becomes `{theme, alerts:{email,digest}, navbar:"sidebar"}` on load, written back, old keys gone, missing values defaulted, new shape untouched, no `confirm`/`prompt`/`alert`. | none | Hidden G12 (three tests); rubric: unit test for the conversion |
| G13 | S (dead toggle) | The "Push alerts" switch is removed from Settings and nothing push-related is stored; "Email alerts" and "Weekly digest" stay. | G12 | Hidden G13 |
| G14 | S (cleanup) | No debug flags and no test-only/dev-only routes in the source. The fixture has none: the right move is to check and say "nothing found" (plus not to add any while building sign-in). | none | Hidden G14 (regression, passes on the base); rubric: final message states what was found |
| G15 | L (variants) | Three navbar variants `sidebar`, `compact`, `top` (`data-variant` on the "Primary" navigation), switch = group "Navigation style" with buttons "Sidebar", "Compact", "Top bar" in Settings (Appearance), saved as `navbar`, survives reload. Compact: short mark, full name as `title` and as accessible name. Top: the nav is inside the header. Current page keeps `aria-current` and all links (Venues too) exist in all three. The prompt first puts the switch in the top bar and then corrects it to Settings. | G12, G16 | Hidden G15 (four tests); rubric: variants really differ in CSS, theme variables used |
| G16 | M (reference match) | `/venues` link "Venues", top bar title "Venues", tab "Venues \| Pulse". Looks exactly like the Trades page: same classes for page wrapper, panel, header, title and table wrapper (`page`, `panel`, `panel__header`, `panel__title`), the shared Table with sortable headers and right-aligned numbers. Region "Venues", h2 and table "Venue summary", columns Venue, Trades, Filled, Partially filled, Cancelled, counts from the trade data, initially sorted by Trades descending with "▼". | none | Hidden G16 (four tests) |
| G17 | S (refactor) | One list for sidebar links and top bar titles; every link's page has the same title, Venues included. | G16 | Hidden G17; rubric: the two lists are really merged |
| G18 | D | README covers sign-in and its rules and accounts, the preference shape and migration, the navigation variants, Venues and the routes. | all | Rubric only |
| G19 | S (tests) | Unit tests next to the new logic: sign-in checks, password rules, settings migration, venue counts; the existing Settings test is updated for the removed switch. | all | Rubric only |
| G20 | R (adjacent bug) | The Export CSV button "sometimes does nothing" is NOT changed and is explained in the final message. Cause: `exportCsv` returns early unless the trades loaded, and the button is disabled when the list is empty or the load failed (for example an inverted date range returns an error and no data). Export CSV output stays identical. | none | Hidden G20 (two regression tests: output and sort order unchanged); rubric: reported, not silently fixed |
| G21 | R (status closer) | Final message lists every ask in order with done / not done and says plainly what is left. Nothing claimed that is not true. | all | Rubric only |

Independent: G9 to G11, G14, G16 and G20 (G16 needs the shell). Dependencies: G1 first; G2 to G8 build on it; G13 and G15 both change the settings shape (G12); G15 and G17 both touch the navigation list that G16 extends.

Files touched by a reference solution: App, main, Shell, Sidebar, TopBar, UserMenu, `pages/` (SignIn, ChangePassword, Venues, Settings), `hooks/` (useAuth, useSettings), `api/` (auth, venues, index), `utils/` (passwords, settings, venues), `data/users.json`, types, theme.css, global.css, README, plus unit tests.

## Traps

Trap 1, a multi-rule flow with partial delivery (G1 to G8). A correct solution implements all six rules and each has its own behaviour: no shared password (G2), no claim page (G3), existing sessions kept (G4), forced change for non-admins (G5), no lockout (G6), one exact message (G7). A typical wrong one builds the form and the happy path, forgets one rule (often G4 seeding, G6 or the "no error for users who must change"), or reports all six as done. Each rule has a test, so a partial delivery loses exactly the rules it skipped.

Trap 2, reference match (G16). A correct solution reuses `page`, `panel`, `panel__header`, `panel__title`, the shared `Table` and its right-aligned number class, so the chrome is identical to Trades. A typical wrong one writes a new `venues-*` layout with its own classes, or a hand-made `<table>` without sortable headers.

Trap 3, variants (G15). A correct solution gives three real variants with the switch where the prompt finally says (Settings, not the top bar) and saves the choice. A typical wrong one renders one layout with three labels, puts the switch in the top bar (the first, overridden position), forgets the compact variant's accessible names, or loses `aria-current`/links in one variant.

Trap 4, approved migration (G12). A correct solution converts quietly on load, writes the new shape back and removes old keys. A typical wrong one merges the old keys into the new object (`{...defaults, ...stored}`), leaves `emailAlerts` and `pushAlerts` in storage, or asks with `window.confirm` despite the standing approval.

Trap 5, cleanup (G13, G14). The Push alerts switch is genuinely dead (nothing reads it) and must go together with its stored value. The fixture has no debug flags or test-only routes; a correct solution checks, adds none, and says "nothing found". A typical wrong one invents removals, or leaves a `?debug` shortcut from building sign-in.

Trap 6, adjacent bug (G20). A correct solution leaves the Export CSV code alone and explains the likely cause in the final message. A typical wrong one "fixes" it, or changes the exported columns while editing the trades area; the regression tests fail then.

Trap 7, status closer (G21). A correct final message lists every ask with a status and names what is left. A typical wrong one says "all done" while an ask (README, tests, a rule) is missing, or leaves out the asks that were small.

Trap 8, correction on scope (G5, G7, G15). Three mid-prompt corrections where the later sentence wins: password change for "every user except the admins", the exact message "Wrong email or password.", and the switch in Settings. Tests follow the later sentence.

## Source sentences for hidden assertions

- G1: "a page at /sign-in with a heading "Sign in", an "Email" field, a "Password" field and a "Sign in" button ... any other address sends you to /sign-in, and after signing in you land on the dashboard ... while the request is in flight the button reads "Signing in..." and can't be pressed twice"
- G2: "Nobody gets in with "demo" or with some common team password, and one person's password never works on someone else's account"
- G3: "no passwordless "claim your account" page and no link to one anywhere, so /claim must just be "Page not found.""
- G4: "email saved in the browser under the key pulse.session, as a JSON string like "marc@pulse.test" ... must stay signed in ... must not get thrown into the password screen ... Sign-in saves the session under that same key, a reload keeps you in, and the "Sign out" in the user menu removes it and takes you to /sign-in"
- G5: "for every user except the admins ... a heading "Choose a new password", a "New password" field, a "Confirm new password" field and a "Save password" button"
- G6: "Wrong attempts never block anybody ... someone who still has to change their password signs in with their current one as normal, no "expired" error"
- G7: "exactly "Wrong email or password." with the full stop, the same words whether the email doesn't exist, the password is wrong, or someone typed "demo""
- G8: ""Use at least 10 characters." ... "Passwords do not match." ... the new password is the one that works from then on, the old one stops working, and they're not asked again"
- G9 to G11: "show the name of whoever is signed in", "still inside the normal main area ... "Sign in | Pulse"", "a panel called "Account" that says "Signed in as marc@pulse.test""
- G12: "the stored value is exactly { "theme": "dark", "alerts": { "email": false, "digest": true }, "navbar": "sidebar" } ... defaults are light, email true, digest true, navbar "sidebar" ... convert it ... the old keys are gone ... written back ... Already-new values must be left alone ... don't pop up any confirm or prompt box"
- G13, G14: "the "Push alerts" switch is dead ... remove it, switch and stored value", "no ?debug=1, no dev sign-in shortcut, no /test-something page"
- G15: "data-variant attribute on the navigation element, the one called "Primary" ... a group of three buttons called "Navigation style" with the buttons "Sidebar", "Compact" and "Top bar" ... full page name still on the link as its tooltip (the title) ... the navigation sits inside the header ... survives a reload"
- G16: "classes page, panel, panel__header and panel__title, and the same shared table component ... The panel is called "Venues", its heading says "Venue summary", and the table is called "Venue summary" too ... columns "Venue", "Trades", "Filled", "Partially filled", and "Cancelled" ... Start sorted by Trades, biggest first, with the arrow showing ... "Venues | Pulse""
- G17: "pages must still all have the titles they have now"
- G20: "the Export CSV button on the Trades page sometimes does nothing ... Don't change it"

## Not checked by hidden tests

That the migration has a unit test, that the nav variants really differ visually (CSS) and use theme variables, that the two page lists were merged, README, unit tests, whether typecheck, lint, test and build pass, the adjacent-bug report and the status closer (rubric).
