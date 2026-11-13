# Spikes, prototypes and candidate designs

## Spike
Use it when a premise is unknown and the plan depends on it. A spike is throwaway code that answers one question.
1. State the question in one sentence.
2. Build the smallest artifact: a pure logic module for a state or data question, a few structurally different variants for a look question.
3. State what result settles it and what result sends the plan back.
4. Mark it a prototype, outside production paths, with no tests, no error handling beyond running, and no persistence. If persistence is the question, use a scratch database or file named "PROTOTYPE, wipe me".

A critic proposes a spike and never runs it; the main session or a builder runs it.

## Pick the shape
- Logic or state model ("does this handle X then Y?"): one self-contained HTML file the owner can click through, with the logic in a portable module, the question stated in a visible intro, and the full state printed after every action. Push it through the hard cases. Add tabbed walkthroughs for the happy path, a tricky edge and an illegal attempt, each reset to a known start state.
- Look ("what should this be?"): several radically different variants on the real page, switched by a `?variant=` URL param and a small floating bar. Real header, data and density, never an empty page. Gate the switcher off in production builds; three variants by default, five at most, structurally different.
- Unclear and the owner is away: pick by the nearby code (backend module: logic; page or component: look) and state the assumption at the top.
- Variants never share a layout; a shared header is fine. A variant that must change data points at a stub, never the real mutation. In a logic demo, label controls in the domain's words for a non-developer, and keep the logic module free of the DOM.
- Start it with one command or a double click.

## Capture
Fold the validated decision into the real code, rewritten properly; never copy prototype code to production. When a snippet states the decision more exactly than prose can (a state machine, a reducer, a schema, a type shape), put it in the spec or ticket, marked as from a prototype and trimmed to the part that decides. Commit the prototype to a throwaway branch, never main, made in a separate `git worktree add` when builders share the checkout, and leave a pointer to it plus the verdict and the question it settled in the ticket or a commit.

## Candidate designs
Use when one attempt at a hard-to-reverse artifact would lock in the wrong shape. Skip it for mechanical work whose shape is already concrete, and never run a second round over a settled design.
1. Write the rubric first: 3 to 6 gradeable criteria. Candidates see only the task, not the rubric.
2. Run N builders at once, each with the same task but a different constraint (smallest interface, most flexible, trivial common case, ports and adapters) so the shapes differ radically, its own worktree or output folder, and a short rationale of alternatives rejected. Each brief carries the project's glossary and architecture terms, and tells the candidate to commit to its constraint, not to a safe middle. Each returns: the interface with its invariants, ordering and error modes; a usage example; what the implementation hides; dependencies and adapters; trade-offs. If one returns nothing, go on with N-1.
3. A judge on a different model than the author (for example Sonnet when Opus built it, via the Agent tool's model option) scores them against the rubric. Read every candidate end to end and score criterion by criterion, not by feel. If you and the judge disagree, read both rationales.
4. Pick the base a later maintainer can extend most easily: cleaner boundary, smaller API.
5. Graft one or two strongest parts from each loser, by hand, so the result holds one model. If all converge, ship the consensus. If they diverge wildly, the task was under-specified: reframe and rerun, do not average.
6. Verify the result like any output. Write a note: the base and why, each graft and its source, what was rejected.
