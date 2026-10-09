Source: derived from mattpocock/skills@49dd158d1076 skills/engineering/wayfinder/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/wayfinder.md

# Wayfinder

A wayfinder map charts work too big for one session as a list of decisions. Each ticket settles one decision. The map is done when nothing is left to decide; then a plan card takes over.

## When

Use it only on a large run: one reached by `route --size large --reason TEXT`, or one started with `--owner-request` because the owner asked for a map. Never start with the map. Size the work first; most work fits tiny or medium and needs no map. If charting finds no open question, drop the map and route back to medium.

## The map file

One local markdown file per effort, at `docs/maps/<name>.md`. It is an index, not a store: each decision lives in its ticket, and the map gives one line and a link.

- **Destination:** one or two lines on what the end looks like: a spec, a locked decision, or a change made in place. Name it first; it fixes the scope.
- **Notes:** the domain, the skills each session reads, standing preferences.
- **Decisions so far:** one line per closed ticket, with the ticket link and the gist of the answer.
- **Fog:** questions you can see coming but cannot yet state sharply. They are in scope.
- **Out of scope:** work ruled past the destination, one line each with the reason. It never comes back as fog.

Tickets live beside the map in `docs/maps/<name>/`, one file each, with a `## Question` section, a type, a `blocked by` line and, once closed, an `## Answer` section. Refer to a ticket by its title, never by a bare number.

## Fog or ticket

Write a ticket when you can state the question precisely now, even if it is blocked. Leave it as fog when you cannot. Do not cut fog into ticket-sized pieces ahead of time. A closed ticket often turns fog into new tickets; move each one out of the fog section when you write it.

## Ticket types

- **Research** (no human): a fact a decision waits on, from docs, APIs or other repositories. It runs as an `investigator` card.
- **Prototype** (with the owner): a rough artifact to react to, such as an outline, a stub or a screen.
- **Grilling** (with the owner): questions in frontier rounds, each with a recommended answer. The main session asks; a worker never answers for the owner.
- **Task**: work that must happen before a decision, such as getting access or moving sample data. A worker does it when it can; otherwise the owner gets a wizard script.

## Sessions

One human decision ticket per session. Research tickets are the exception: start every research ticket on the frontier together, as `investigator` cards in one Workflow, and let each write its findings to its ticket file.

1. Read the map, not every ticket.
2. Take the named ticket, or the first one on the frontier: open, unblocked and unclaimed. Mark it claimed before any work.
3. Resolve it by its type. Open closed tickets only when the answer needs them.
4. Write the answer in the ticket, close it, and add its line to Decisions so far.
5. Add the tickets the answer made sharp, and update or close tickets it made wrong. Close a ticket that sits past the destination and give it an Out of scope line.

## Hand-off

When the frontier and the fog are both empty, the way is clear. Hand the map to a designer-planner `plan` card. The map produces decisions; the build starts from the plan, not from the map.
