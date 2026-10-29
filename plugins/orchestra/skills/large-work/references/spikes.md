# Spikes, prototypes and candidate designs

## Spike
Use it when a premise is unknown and the plan depends on it. A spike is throwaway code that answers one question.
1. State the question in one sentence.
2. Build the smallest artifact: a pure logic module for a state or data question, a few structurally different variants for a look question.
3. State what result settles it and what result sends the plan back.
4. Mark it a prototype, outside production paths, with no tests, no error handling beyond running, and no persistence. If persistence is the question, use a scratch database or file named "PROTOTYPE, wipe me".

A critic proposes a spike and never runs it; the main session or a builder runs it.

## Pick the shape
- Logic or state model ("does this handle X then Y?"): one self-contained HTML file the owner can click through, with the logic in a portable module, the question stated in a visible intro, and the full state printed after every action. Push it through the hard cases.
- Look ("what should this be?"): several radically different variants on the real page, switched by a `?variant=` URL param and a small floating bar. Real header, data and density, never an empty page.
- Unclear and the owner is away: pick by the nearby code (backend module: logic; page or component: look) and state the assumption at the top.
- Start it with one command or a double click.

## Capture
Fold the validated decision into the real code. Commit the prototype to a throwaway branch, never main, and leave a pointer to it plus the verdict and the question it settled in the ticket or a commit.

## Candidate designs
Use when one attempt at a hard-to-reverse artifact would lock in the wrong shape. Skip it for mechanical work whose shape is already concrete, and never run a second round over a settled design.
1. Write the rubric first: 3 to 6 gradeable criteria. Candidates see only the task, not the rubric.
2. Run N builders at once, each with the same prompt, its own worktree or output folder, and a short rationale of alternatives rejected. If one returns nothing, go on with N-1.
3. A judge from another model family scores them against the rubric. Read every candidate end to end and score criterion by criterion, not by feel. If you and the judge disagree, read both rationales.
4. Pick the base a later maintainer can extend most easily: cleaner boundary, smaller API.
5. Graft one or two strongest parts from each loser, by hand, so the result holds one model. If all converge, ship the consensus. If they diverge wildly, the task was under-specified: reframe and rerun, do not average.
6. Verify the result like any output. Write a note: the base and why, each graft and its source, what was rejected.
