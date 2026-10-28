Okay so this round is mostly about the watchlist and notifications side of Pulse, plus a couple of bugs that people have been complaining about. I'll just ramble through it, sorry if it jumps around.

First of all the watch button on the instrument page, "Watch" and "Watching" confuses people, they think Watching means something is loading. Make it "Add to watchlist" when it's not on the list and "On watchlist" when it is, keep the star.

Notifications. A few small things in the bell:
- each notification should have a little icon for what kind it is, trade, report, client, system, next to the kind label. SVG, decorative, screen readers just hear the label like now.
- "Mark all as read" is too long for that header, call it "Mark all read".
- the red bubble with the unread count uses the same red as falling prices, which is wrong, it's not a price. Give it its own token, --color-badge, #d92d20 in light and #ff6b61 in dark, and use that for the bubble.

And on the bell, the actual bug: when I click "Mark all as read" nothing happens, the count stays at 3 and the items still look unread, but if I reload the page it's 0. So it's saving but the screen doesn't update. Fix it properly, I want to know why it happened.

On the dashboard watchlist, the rows just show the symbol, and half the team doesn't know what XAU is. Put the instrument name under the symbol, like Top movers does.

Settings, the email alerts switch says "Price moves above your thresholds." but there are no thresholds anywhere, which is what the alerts thing below is for. Change it to "When one of your price alerts goes off."

Second bug, the price chart on the instrument page is upside down. Apple is up like 28% over the period and the chart goes down to the bottom right. Every chart that goes up looks like it goes down and the other way round.

Then prices. The dashboard instruments table shows EURUSD as $1.08 but the instrument page says $1.0842, and gold also looks different. We have two sets of formatting helpers in two files doing overlapping things. I want all the money and number formatting in one module, one way to show a price, used everywhere, so a price always has the same digits wherever it shows. Arithmetic stuff can stay where it is.

Now the bigger pieces. One, price alerts. New page "Alerts" in the sidebar, at /alerts, top bar says "Alerts". There's a form: "Instrument" dropdown (symbol then name for each option), "Condition" dropdown with "goes above" and "goes below", a "Price" box and an "Add alert" button. Each alert shows in a list like "AAPL goes above $250.00", with the price shown the same way as everywhere else, so EURUSD would be like "EURUSD goes below $1.1000". Next to each one a badge, "Triggered" if the current price is already past it, otherwise "Watching", and a "Remove" button. Empty list says "No alerts yet." If the price is empty or zero say "Enter a price above zero" and don't add anything. They stay after a reload, put them wherever you think is right. And this is the important bit: when an alert is triggered it should show up in the notifications bell as an unread notification titled like "AAPL is above $250.00", so the count goes up by one, and it should only ever be there once, a reload must not add it again or make it unread again once I've read it. Mark all read has to clear those too.

Two, a proper watchlist page. Sidebar link "Watchlist", /watchlist, top bar "Watchlist". A table called "Watched instruments" for screen readers, one row per watched instrument: the symbol and name, last price, day change, and a little 1 month trend line, the small sparkline, labelled like "AAPL 1 month trend". Above it an "Add instrument" dropdown with only the instruments that aren't already on the list, symbol then name again, and an "Add" button. Each row gets a "Remove" button. If the list is empty say "Your watchlist is empty." Clicking a row opens a drawer called "Instrument details" with the instrument name as its title, the key stats like on the instrument page, the same watch button, and a link "Open instrument page". It's the same list as the dashboard watchlist and the watch button, not a new one, so if I add something here the instrument page shows it as on the watchlist.

And last, the README, update it for the alerts and the watchlist page and where things are stored.

Add unit tests for the bug fixes and for any new logic, next to the code.

Work on a new branch, commit as you go, and when everything is done push the branch to origin. Don't ask me questions, I'm away; make sensible calls and note them in the final message.
