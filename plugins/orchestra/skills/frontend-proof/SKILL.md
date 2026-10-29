---
name: frontend-proof
description: "Gives the proof and accessibility rules for interactive UI. Load when building a new interactive component (dialog, menu, drawer, form, keyboard flow) or when the ask is about accessibility. Not for copy, color, spacing or label changes."
---
# Frontend proof

## Prove it on the real screen
- Unit tests do not prove a UI ask. Drive the real app with real input: click, type, keyboard. Use the repo's e2e runner, or a dev server with a browser tool.
- Check each state the ask names: empty, loading, error, long text, many rows. Also check each theme and viewport the ask names.
- Open and look at each screenshot you keep. Keep it as evidence.
- Report a state you could not reach as "not checked". Never report it as working.

## Keyboard and focus
- Every control has an accessible name. An icon that repeats a visible label is hidden from assistive tech.
- Dialogs and menus move focus in when they open, close on Escape, and return focus to the trigger.
- Keyboard reaches everything a mouse can. Tab order follows the visual order.
- Color is never the only signal.

## Async UI
- A submit never fails silently. Do not disable the button, or return early from the handler, because a field is empty, invalid or still loading: validate first and show each field's error message. Block only a second submit while one is in flight.
- A response that arrives after the user moved on must not overwrite newer state. Ignore stale responses or cancel them.
- Loading and error states never leave old data under a new title.

## Consistency
- A value shown in several places uses one formatter or component. Follow the existing pattern for tables, dialogs, badges, dates and money.
- A rule the owner states for "every" or "all" places also applies to new screens.
- Split a page that grows past 500 lines by responsibility before you add more.

## Design alternatives
- When the owner asks for alternatives, build them behind one switch on the real route, structurally different. Keep the chosen one. Delete the rest and the switch.

Sources: pstack-claude@47c6f80, orchestra v2.15.3.
