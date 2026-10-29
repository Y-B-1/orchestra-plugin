# Cleanliness and slop lens

Report findings only. Cleanup belongs to a build cleanup card. Start from the diff. At most five candidates, best three first. None is a valid answer.

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
- A comment that states a rule of a dependency, platform or protocol is kept. Say where to check it.
- A comment saying "do not remove" or "workaround for X" is a flag: the root cause or a lint, type or test that enforces it is the fix.
- A new lint or type suppression needs a reason beside it.

## Growth
- New ad-hoc conditionals, one-off booleans or special cases in an unrelated flow: a missing model or helper. Suggest the home for the logic.
- Feature logic leaking into a general module.
- A file pushed past about 500 lines (the standards lens budget): suggest the split. Past 1000 is a strong finding.
- Generic "magic" that hides a simple data shape. Identity wrappers and pass-throughs.
- Independent work run in sequence for no reason, or two related writes that can leave half state.

## Code judo
Once per diff, ask: is there a reframe that deletes whole branches, helpers or layers while behavior stays? Prefer deleting complexity over moving it. Name the reframe in one sentence. It is a note unless it removes real risk.

## Efficiency
Trace hot or repeated work, unbounded loops, missing timeouts. Skip cost that does not matter at the real input size.

## Safety line
Never recommend deleting tests or validation. Never widen the scope past the diff.
