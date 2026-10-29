# Wayfinder map

A map charts work too big for one session as a list of decisions. Each ticket settles one decision. The map is done when nothing is left to decide; then a plan unit takes over. The map produces decisions, not deliverables. The pull to just do the work means you reached the map's edge: hand off.

## The map file
One markdown file per effort, `docs/maps/<name>.md`. It is an index: a decision lives in its ticket; the map gives one line and a link.
- **Destination:** one or two lines on the end state (a spec, a locked decision, a change made in place). Name it first; it fixes the scope.
- **Notes:** the domain, the skills each session reads, standing preferences.
- **Decisions so far:** one line per closed ticket, with link and the gist of the answer.
- **Fog:** questions you see coming but cannot yet state sharply. They are in scope.
- **Out of scope:** work ruled past the destination, one line each with the reason. It never comes back as fog.

Tickets sit in `docs/maps/<name>/`, one file each: `## Question`, a type, a `blocked by` line, and once closed `## Answer`. If the repo has an issue tracker, use it instead: the map is one issue, tickets are child issues. Refer to a ticket by its title, never a bare number.

## Fog or ticket
- Write a ticket when you can state the question precisely now, even if you cannot answer it or it is blocked.
- Leave it as fog when you cannot phrase it sharply. Do not cut fog into ticket-sized pieces ahead of time.
- A closed ticket often turns fog into tickets; remove each graduated item from the fog.
- A ticket past the destination is closed with an Out of scope line, not resolved.

## Ticket types
- **Research** (no owner): a fact a decision waits on, from docs, APIs or other repositories. An investigator unit resolves it. Start all open research tickets together.
- **Prototype** (with owner): a cheap rough artifact to react to. Read `references/spikes.md`.
- **Grilling** (with owner): questions in frontier rounds, each with a recommended answer. The main session asks; a worker never answers for the owner.
- **Task**: work that must happen before a decision, such as access or sample data. A worker does it when it can; otherwise the owner gets a wizard script.

## Charting
1. Name the destination with the owner.
2. Map the frontier breadth first: surface the open decisions and the first steps takeable now.
3. Create the map, then the tickets you can state now. Wire the `blocked by` lines in a second pass, with real titles.
4. Start the research tickets in parallel. Stop: charting resolves no human ticket.

## Working the map
One human ticket per session; research tickets are the exception.
1. Read the map, not every ticket.
2. Take the named ticket, else the first frontier ticket (open, unblocked, unclaimed). Mark it claimed before any work.
3. Resolve it by its type. Open closed tickets only when the answer needs them.
4. Write the answer in the ticket, close it, add its line to Decisions so far.
5. Add the tickets the answer made sharp; update or close tickets it made wrong.

When the frontier and the fog are both empty, give the map to a plan unit. Build from the plan, not the map.
