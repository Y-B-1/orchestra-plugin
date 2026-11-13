# Cleanliness and slop lens

Report findings only. Cleanup belongs to a cleanup builder. Start from the diff. At most five candidates, best three first. None is a valid answer.

## Tags
Tag each finding: delete, stdlib, native, speculative, shrink, slop, comment, growth.
- delete: nothing calls it. Search real usage first.
- stdlib: hand-written code the standard library gives.
- native: a dependency or helper that duplicates a platform feature.
- speculative: an abstraction, option or hook with one use or none.
- shrink: a smaller equivalent that saves five lines or more.
- slop: AI residue, see below.
- comment: see below.
- growth: see below.

## Slop (compare the diff with the file around it)
- Defensive checks or try/catch on a trusted internal path.
- `any` or a cast added only to silence the type checker.
- Deep nesting that early returns would flatten.
- Naming, helpers or style that differ from neighbors.
- A fallback that hides a broken invariant instead of failing.

## Comments
- Flag a comment that restates the code, narrates the change, or disagrees with the code.
- A comment that states a rule of a dependency, platform or protocol is kept only once the rule is confirmed in that source's docs or code. A refuted one is deleted, citing the source. With the source unreachable it stays, marked HOLD with where to check.
- A surprise in our own code is never kept as prose: flag the symbol for a rename, extract or type change.
- A comment saying "do not remove" or "workaround for X" is a flag: the root cause or a lint, type or test that enforces it is the fix.
- A new lint or type suppression needs a reason beside it.

## Blocks by default
Correct behavior alone does not approve. These block unless the author justifies them:
- A file pushed past the size cap (about 500 lines; past 1000 is strong).
- Ad-hoc branching added to an existing flow.
- Feature checks scattered across shared code.
- An unneeded wrapper, or a contract held up by casts.
- A duplicated canonical helper, or logic in the wrong layer.

## Growth
- New ad-hoc conditionals, one-off booleans or special cases in an unrelated flow: a missing model or helper. Suggest the home for the logic.
- Feature logic leaking into a general module.
- A file past about 500 lines: suggest the split by responsibility.
- Generic "magic" that hides a simple data shape. Identity wrappers and pass-throughs.
- Independent work run in sequence for no reason, or two related writes that can leave half state.

## Code judo
Once per diff, ask: is there a reframe that deletes whole branches, helpers or layers while behavior stays? Prefer deleting complexity over moving it. Name the reframe in one sentence. When it deletes whole branches or layers and the author has not justified the current shape, it blocks in a deep or thermo review; otherwise it is a note.

## Baseline smells
Always a labelled judgement call, overridden by a repo rule: mysterious name, duplicated code, feature envy, data clumps, primitive obsession, repeated switches, shotgun surgery, divergent change, speculative generality, message chains, middle man, refused bequest.

## Efficiency
Trace hot or repeated work, unbounded loops, missing timeouts. Skip cost that does not matter at the real input size.

## Safety line
Never recommend deleting tests or validation. Never widen the scope past the diff.
