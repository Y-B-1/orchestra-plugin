# Frontend

Load when an ask changes pages, components, styles or interaction.

## Prove it on the real screen
Unit tests do not prove a UI ask. For each changed screen, drive the real app (the repo's e2e runner, a dev server and a browser tool, or the hidden-test style harness the repo uses) with real input events: click, type, keyboard. Check each state the ask names: empty, loading, error, long text, many rows. A state you could not reach is reported as "not checked", never as working.

## Keep it consistent
- A value shown in several places uses one formatter or component. New code follows the existing pattern for the same thing (tables, dialogs, badges, dates, money).
- A rule the user states for "every" or "all" places applies to new screens too.
- Split a page that grows past about 300 lines into parts by responsibility (sections, hooks, columns) before adding more.

## Accessibility is part of done
Every control has a name; icons that repeat a label are hidden from assistive tech. Dialogs and menus move focus in, close on Escape and return focus. Keyboard reaches everything a mouse can. Color is never the only signal.

## Async UI
A request whose result arrives after the user moved on must not overwrite newer state (ignore stale responses or cancel them). Loading and error states never leave the old data under a new title.

## Variants
When the user asks for design alternatives, build them behind one switch on the real route, structurally different, then keep the chosen one and delete the rest and the switch.
