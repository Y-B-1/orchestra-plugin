# Cleanup mode

Use after review, to remove what the diff made dead, duplicated, over-abstracted or sloppy. The brief lists the paths and, when review ran, the findings. With no findings, the paths are the changed files. Edit those paths only. Source cleanup comes first; test hygiene is a separate step under `orchestra:test-quality`. Every run is scoped to the touched files (`gate unit --scoped`); the one full run belongs to the main session.

## Procedure
1. Read each cited finding (or each changed file) and the code around it. Start from the branch diff against the base: the base sha in your brief, else the PR's base branch, else the default branch. Uncommitted changes count.
2. Run the scoped checks first. After each edit, rerun them. Revert (restore the file) an edit whose check fails; never fix forward. Both runs pass with tests unchanged, except the tests of a module you removed or merged (step 4: remove or move them, and add tests at the new interface). A cleanup that needs any other test edit changed behavior: stop and report. For a UI file, report "e2e not run by cleanup": the main session owns the one scoped e2e run.
3. Prove disuse before you delete: search the repository for callers. A caller found only in tests means the test keeps dead code alive; say so and delete neither without a finding that names it.
4. Deletion test: if removing a module only moves its complexity to the callers, it earns its place. If the complexity vanishes, it was a pass-through; remove it (or merge it into its one caller), and remove or move the tests that only exercised it, with tests at the new interface when a merge changed it. Report the test count before and after.
5. Extract a helper only with two verified callers. Reuse an existing helper first. Count the net lines saved.
6. Handle at most five candidates, best three first. None is a valid answer.
7. Mention an unrelated candidate in the report. Do not touch it.
8. Reader load: a new layer, wrapper or state must cut what a reader holds by at least as much. Report a one-caller wrapper, state that could be a local or derived, and a module cut by step (load, validate, save) instead of by knowledge.
9. Report, never fix, these structure flags from `<plugin>/skills/review/references/architecture-depth.md`: state with two writers, a list kept in step by hand, internals an outsider can import, two ways to do one task.

## Slop to remove from the diff
- Comments that restate the code, narrate the change or cite the task. Keep a comment only when it states a constraint of something we cannot change (a platform, vendor or protocol rule) or a reason the code cannot show. Confirm that rule in the source's docs or code first: delete a refuted comment and cite the page; if the source is unreachable, keep it labelled HOLD with where to check.
- A comment that claims "do not remove" (or is marked IMPORTANT) about the repo's own code: offer the cheapest type, test or lint that enforces it, then delete the comment. If no enforcement is in scope, report the constraint as open. A comment that states a platform, vendor or protocol constraint stays. Before you delete a "do not remove" or IMPORTANT comment, run investigate why mode on its symbol. If the reason is still unclear, keep the comment and report it open.
- Defensive checks or try/catch on trusted paths, `any` casts used only to silence types, deep nesting that early returns flatten, patterns foreign to the file.
- A suppression of lint or types without a reason. A suppression that hides a correctness or safety fault is a finding, not a keep.
- Prefer root-cause fixes over a guard that hides a symptom.

## Tags
One tag per change: delete, stdlib (use the standard library), native (use the platform feature), speculative (inline an abstraction with one use), shrink (a shorter equivalent that saves five lines or more).

## Never
- Delete the only guard of a behavior, a validation, an error path, a security check or an accessibility feature.
- Change behavior, interfaces or output other code reads. Rename or restructure for taste.

## Report
Per finding: tag, lines removed, the search command and hit count behind each deletion, net line change, the check command with its exit code. A finding you did not act on gets a one-line reason.
