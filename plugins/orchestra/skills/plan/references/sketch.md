# Sketch types and signatures

Failure it prevents: code written before the shape is agreed, then patched.

1. Ground. Read every system the change touches, and read the history of any shape you would move. Naming a file is not grounding.
2. Write the caller's usage first. Derive the types from it.
3. Design it twice. Sketch at least two structurally different shapes, even when the first looks enough. Screen each for: a change that looks right in one file but is wrong for the repo, a nearest-example copy that breaks, state with more than one writer, two ways to do one task, a hand-synced list, internals a caller can import, escape hatches (`any`, casts, optional fields always set). Prefer the shape with the smaller public surface that hides more behavior. Pick one, or a hybrid, with the reason. For a hard-to-reverse shape, ask the main session to run Candidate designs (`plugins/orchestra/skills/large-work/references/spikes.md`) with this sketch task instead of sketching alone.
4. Deep modules: name the seam and what sits behind it. Deletion test: if deleting a module only moves its complexity to callers it earns its place; if the complexity vanishes it was a pass-through. One adapter is a hypothetical seam; two make a real one.
5. Output: one file of types and signatures with unimplemented bodies and pseudocode for a small change; a module map plus types for a larger one. Add a short rationale: usage, chosen shape, rejected shape.
6. The sketch is the contract. A needed deviation is a signal: ask whether the sketch was wrong, the requirement missed, or the implementer overreaching. Once an owner accepts a change, update the sketch before the next unit starts, so no worker gets contradicting instructions.
7. Scrap rule: the same workaround shape repeating, unrelated special cases, or two deviations of one shape mean the sketch is wrong. Re-ground, redesign as if the new constraint were day one, make the new sketch smaller than the old, and sketch again.
