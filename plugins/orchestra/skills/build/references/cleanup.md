# Cleanup mode

Use after review, to remove what the diff made dead, duplicated, over-abstracted or sloppy. The brief lists the findings and the paths. Edit those paths only.

## Procedure
1. Read each cited finding and the code around it. Start from the branch diff against the base.
2. Run the checks first. After the pass, run them again; both runs pass with tests unchanged. A cleanup that needs a test edit changed behavior: stop and report.
3. Prove disuse before you delete: search the repository for callers. A caller found only in tests means the test keeps dead code alive; say so and delete neither without a finding that names it.
4. Deletion test: if removing a module only moves its complexity to the callers, it earns its place. If the complexity vanishes, it was a pass-through; remove it.
5. Extract a helper only with two verified callers. Reuse an existing helper first. Count the net lines saved.
6. Handle at most five candidates, best three first. None is a valid answer.
7. Mention an unrelated candidate in the report. Do not touch it.

## Slop to remove from the diff
- Comments that restate the code, narrate the change or cite the task. Keep a comment only when it states a constraint of something we cannot change (a platform, vendor or protocol rule) or a reason the code cannot show.
- A comment that claims "do not remove" or a constraint: offer the cheapest type, test or lint that enforces it, then delete the comment. If no enforcement is in scope, report the constraint as open. Before you delete a "do not remove" or IMPORTANT comment, run investigate why mode on its symbol. If the reason is still unclear, keep the comment and report it open.
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
