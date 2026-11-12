# Pre-commit hooks

Only when the owner asks. If the repo already has hooks (`.husky/`, `.pre-commit-config.yaml`, `lefthook.yml`), extend them; do not add a second system.

Orchestra builders commit in one shared checkout while siblings are mid-edit. So the pre-commit hook checks staged files only. Whole-project typecheck and tests go in a pre-push hook or CI, never pre-commit.

For a Node repo, default to Husky with lint-staged:
1. Detect the package manager from the lockfile (`pnpm-lock.yaml`, `yarn.lock`, `bun.lock` or `bun.lockb`, else npm). Run tools with its exec command (`pnpm exec`, `yarn`, `bunx`, `npx`).
2. Install `husky lint-staged` as dev dependencies; run `husky init` (it adds `"prepare": "husky"`).
3. `.husky/pre-commit` runs `lint-staged` only. For the project's `typecheck` and `test` scripts, write `.husky/pre-push`. Omit a line whose script does not exist and tell the owner.
4. `.lintstagedrc` runs the repo's own formatter on staged files (Prettier, Biome, dprint, oxfmt), for example `{ "*": "prettier --ignore-unknown --write" }`. Install Prettier, with a config in the repo's current style, only when the repo has no formatter.
5. Verify: the hook file is executable, `lint-staged` runs, and a test commit passes through the hook.
6. Commit only these files: "Add pre-commit hooks".

For a non-Node repo, use the `pre-commit` framework or the repo's own tooling with the same shape: format staged files at commit, typecheck and test at push.
Keep hooks fast. Never tell anyone to bypass them with `--no-verify`. A builder whose commit is rejected by a hook on a sibling's file waits and retries once; if it still fails, it reports "not committed: hook failed on <file>" and the main session commits.
