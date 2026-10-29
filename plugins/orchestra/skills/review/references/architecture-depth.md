# Architecture depth lens

Report findings only. Use these terms exactly: module (anything with an interface and an implementation), interface (everything a caller must know: types, invariants, order, errors, config, cost), seam (where behavior can change without editing in place), adapter (a thing that fills a seam), depth (behavior per unit of interface), leverage (what callers gain), locality (change and bugs concentrate in one place).

## Checks
- Deletion test: delete the module in your head. Complexity vanishes: pass-through, flag it. It reappears in N callers: the module earns its place.
- Shallow module: the interface is nearly as complex as the body. Suggest merging it into its neighbor or hiding more behind it.
- Interface is the test surface. A test that needs internals when the body changes tests past the interface. Flag it.
- One adapter is a hypothetical seam; two (usually production and test) is a real one. Flag a port with one adapter and no test use.
- Locality: a pure function extracted only for tests, while the bugs hide in how callers use it, is a locality loss.
- Leaking: a caller must know an order, a flag or a private shape to use the module correctly. The knowledge belongs behind the interface.
- Pass-through layers: adjacent layers that repeat the same methods and arguments. A one-caller wrapper. Flag both.

## Dependency category sets the test seam
1. In-process (pure, in-memory): merge and test through the interface. No adapter.
2. Local-substitutable (a local stand-in exists): test with the stand-in. Internal seam, no external port.
3. Remote but owned: a port at the seam, an HTTP adapter for production, an in-memory adapter for tests.
4. True external (third party): an injected port; tests give a mock adapter.

## Testability
- Dependencies are passed in, not created inside.
- Results are returned, not applied as side effects.
- After a deepening, tests at the new interface replace the old shallow-module tests. Layered duplicates are waste.

## Reader load
Can a new reader answer "where does X come from" and "what can change X" in 30 seconds? Count layers to trace and state to hold. Prefer returns to mutation, locals to fields, fields to module state. Name an invariant once at the boundary, not in each consumer. A new layer or state must cut reader load elsewhere by at least as much.

## When the design is costly to reverse
Ask whether the author compared at least two interface shapes, judged on depth, locality and seam placement. Ask for the comparison only for such choices.

Do not propose a full redesign unless the finding blocks. Hot spots first: weigh files that changed often in `git log` over untouched ones.
