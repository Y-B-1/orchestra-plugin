# lean.py check

`python3 lean.py check [--base REF] [--max-lines N] [--json]` scans the diff of the current branch against its base and prints one line per finding: `KIND path[:line] message`, grouped by kind, then a summary line. The base is `--base`, else the merge-base with `origin/<default branch>`, else with the local default branch. It compares the working tree, so committed, staged, unstaged and untracked (not ignored) files are all included. It never blocks: it exits 0, or 2 for invalid arguments. The coordinator and the reviewer read it before review. `--json` prints `{"base", "findings", "counts"}`.

**size** A text source file is over the line budget (default 500) and grew in this diff. A file already over budget that did not grow is not flagged. Lockfiles, `*.min.*`, `dist/`, `build/`, generated files and binaries are skipped. Split the file, or add a line `path-glob reason` to `.orchestra/budget-waivers` and say why in the report.

**test-weakened** The diff adds a skip, `.only`, a lint or type suppression, a raised test timeout, or changes a snapshot, a CI workflow or a lint or type config. Each needs a stated reason in the report; otherwise undo it and fix the cause.

**self-mock** A test mocks a module of this repo (a relative `vi.mock`/`jest.mock` path, or a `patch` of the repo's own package). That test then proves the mock, not the code. Use the real module and mock only the outside world.

**debug** Leftover `console.log(`, `debugger;`, `breakpoint()`, `pdb.set_trace`, `[DEBUG-` or a Python `print(` that mentions DEBUG. Remove it before the PR.

**rules** The diff changes `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md` or a file under `.claude/`. The reviewer judges the change against the base version of those rules, not the edited one.

**sensitive** A changed path names auth, login, session, token, secret, password, payment, billing, permission, role, crypto, webhook, `.env`, middleware or migrations. The reviewer loads the security lens for this change.

**secret** An added line looks like a credential (AWS key, private key header, GitHub, `sk-` or Slack token). Only the path and line are printed, never the value. Remove it, rotate the credential, and keep it out of history.
