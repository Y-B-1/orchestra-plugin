# Docs mode

Use when the ask is a README, a guide, a changelog, a doc comment or a PR body.

## Standard
- Cut every word that does no work. Do not write "simply" or "just".
- Name the real file, symbol, flag and command, copied from the code. Never invent one.
- Run every command you document, and say what it prints when that matters.
- Every count, list or tree is true at the commit that lands it. Put the command that regenerates it beside it.
- One document, one purpose: a tutorial, a how-to, a reference or an explanation. Do not mix them.
- Put the condition before the instruction: "If the build fails, run X".
- State the target behavior, not a ban. Write each fact once and link to it elsewhere.
- Date a claim that can go stale, or cite the commit it was true at.

## PR body and commit message
- A PR body follows `orchestra:ship` `references/pr-body.md`.
- The commit subject says what changed in the imperative, with no task id or narration.

## Check before you report
1. Search the doc for each name you wrote and confirm it exists in the code.
2. Rerun each command and count at the final head.
3. Report any claim you could not check as unchecked.
