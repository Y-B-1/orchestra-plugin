---
name: build
description: "Gives the deeper builder rules and the mechanical, cleanup and repair modes. Load when you are a builder and your brief names a mode, or a unit fails its checks twice. Not for a routine first build that passes."
---
# Build

## All builders
- Own only the files in your brief. Never revert, stage or commit a sibling's edit. Fix check errors only in your files.
- Changing behavior or fixing a bug: write the failing test first. Run it and show it red for the right reason. Then write the code and show it green.
- Use the same command text for the red run and the green run. A red run on a wider command is not evidence.
- Fix a bug where the bad value starts, not where it shows. Name other callers of the same code.
- Keep a changed source file under about 500 lines. Split by responsibility before it grows past.
- If the brief leaves a product choice open, report BLOCKED with the open question and your recommendation. Do not guess in code.
- Report the exact commands you ran with their exit codes. Read each exit code from the command, never after a pipe.

## Mechanical mode
Use when one rule is applied the same way across many files.
- Write the rule in one sentence before you edit.
- Count the sites with a search before you start. Save the search command.
- Edit generated files by changing their source and running the generator. Never edit them by hand.
- Apply the rule the same way at every site. Do not fix other things on the way.
- At the end, run the same search again. It must find no site that still needs the change. Report the before and after counts.
- List every file you touched in the report.

## Cleanup mode
Use after review, to remove what the diff made dead, duplicated or over-abstracted.
- Behavior must not change. Run the checks before you start and after you finish. Both runs must pass with the tests unchanged.
- Remove code only when a search proves nothing uses it.
- Remove a wrapper only when it just passes the call through.
- Extract a helper only when two real callers exist.
- Handle at most five candidates in one pass.
- Never delete a test, a validation, a security check or an accessibility check.
- Report each change as one of: delete, use the standard library, use the native feature, remove speculative code, shrink.

## Repair mode
Use when your brief lists findings to fix.
- Fix only the findings given. Change nothing else.
- Restate each finding. Reproduce it against the source before you change anything.
- If you think a finding is wrong, do not skip it silently. Report it with evidence: the line, the test or the command output.
- If a finding conflicts with the spec or with another finding, report BLOCKED. Do not settle it in code.
- Fix blocking findings first (breakage, security), then simple ones, then complex ones. Take one at a time, each with its failing test first.
- If the same fault exists at other sites, name them in the report. Do not edit them.

Sources: orchestra v2.15.3, mattpocock/skills@59db609.
