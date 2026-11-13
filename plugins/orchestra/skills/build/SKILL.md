---
name: build
description: "Gives the deeper builder rules and the mechanical, lever, migrate, cleanup, sensitive and repair modes. Load when you are a builder and your brief names a mode, or a unit fails its checks twice. Not for a routine first build that passes."
---
# Build

## All builders
- Own only the files in your brief. Never revert, stage or commit a sibling's edit. Fix check errors only in your files.
- Changing behavior or fixing a bug: write the failing test first. Run it and show it red for the right reason: report the failure text, trimmed, not the assertion line. Then write the code and show it green.
- Use the same command text for the red run and the green run. A red run on a wider command is not evidence.
- Fix a bug where the bad value starts, not where it shows. Name other callers of the same code.
- Make the smallest change that solves the ask. Put one decision behind one source of truth. Add no abstraction, layer or option the ask does not need.
- Keep a changed source file under about 500 lines. Split by responsibility before it grows past.
- If your change contradicts a recorded decision (an ADR), report BLOCKED or name the reopen. Never override it silently.
- If the brief leaves a product choice open, report BLOCKED with the open question and your recommendation. Do not guess in code.
- Run every check bounded, never in watch mode: `python3 <plugin>/scripts/lean.py run SECONDS -- CMD` (<plugin> is the folder that holds the `lean.py` named in your brief).
- After two failed check runs, stop guessing: load `orchestra:diagnose`, or commit what works and report the rest as not done.
- Report the exact commands you ran with their exit codes. Read each exit code from the command, never after a pipe.

## Mechanical mode
Use when one rule is applied the same way across many files.
- Write the rule in one sentence before you edit.
- Count the sites with a search before you start. Save the search command.
- Edit generated files by changing their source and running the generator. Never edit them by hand.
- Apply the rule the same way at every site. Do not fix other things on the way.
- Move or rename with `git mv`, name the old and new path in the commit, and rerun the repo's structure lint after each move.
- Work in batches (one package or directory). Run the verification command after each batch.
- At the end, run the same search again. It must find no site that still needs the change. Report the before and after counts.
- List every file you touched in the report.

## Lever mode
Use when the brief names it, when one change repeats across more than about five files, or when a script would make a non-trivial edit, migration or one-off check rerunnable.
- Do the first site by hand to learn the recipe. Then write the smallest script or codemod that does it. Rerun it on that site and diff against your hand edit.
- Make the lever safe to rerun. Run it yourself in one pass; do not fan out hand edits a script can do.
- A comparison or check tool must refuse or report "inconclusive" when its input is missing. Seed one known-bad input per claim and confirm the tool reports it.
- Commit the lever only if the brief says the work outlives the session; otherwise name its path in the report. An uncommitted lever script lives outside the repo's write scope (the OS temp folder). A test-typing migration is one example: replacing `as` casts with a partial-data helper across test files. Partial-data helpers (shoehorn `fromPartial` for `as T`, `fromAny` for `as unknown as T`, `fromExact` to force a full object) belong in test files only; run the type check after. The main session installs the package; report BLOCKED if it is missing.
- To enforce module boundaries on request, read `references/boundaries.md`.

## Refactor mode
Use when structure moves and behavior must not.
- Pin behavior first with a characterization test or an equivalence check that diffs old and new output. Type check and lint are not a pin. Run the pin before the move and after each step; revert a step that turns it red.
- After a rename, search strings, prose and docs for the old name. A rename tool misses them.
- Keep the change only if a reader has less to hold afterwards. A bug or missing feature you find on the way is reported, not mixed in.
- When you merge or deepen modules, write tests at the new interface and delete the superseded shallow-module tests in the same unit. Never export an internal only so a test can reach it.

## Migrate mode
Use when a new internal API replaces an old one and no outside user needs the old form.
- Add the new form, move every caller in batches, then delete the old form in the same unit. Keep no compatibility layer.
- Update tests to assert the new contract. Delete a test only if it protects just the old implementation detail and no behavior.
- If an outside caller may exist (published package, public endpoint), report BLOCKED.

## Cleanup mode
Use after review, to remove what the diff made dead, duplicated, over-abstracted or sloppy (comments that restate code, dead code). When the brief names it, read `references/cleanup.md`.

## Docs mode
Use when the ask is documentation or a PR body. Read `references/docs.md`.

## Sensitive mode
Use when the brief names it (the change touches auth, secrets, money or personal data). Read `references/sensitive.md`.

## Repair mode
Use when your brief names Repair mode or lists findings to fix.
- Fix only the findings given. Change nothing else.
- Restate each finding. Reproduce it against the source before you change anything.
- If you think a finding is wrong, do not skip it silently. Report it with evidence: the line, the test or the command output.
- If a finding conflicts with the spec or with another finding, report BLOCKED. Do not settle it in code.
- Fix blocking findings first (breakage, security), then simple ones, then complex ones. Take one at a time, each with its failing test first.
- If the same fault exists at other sites, name them in the report. Do not edit them.

Sources: orchestra v2.15.3 (sensitive, cleanup, mechanical), pstack@47c6f80 (deslop, no-comments, build-the-lever, migrate-callers, laziness), mattpocock/skills@59db609 (migrate-to-shoehorn).
