# Pre-commit hooks

Only when the owner asks. If the repo already has hooks (`.husky/`, `.pre-commit-config.yaml`, `lefthook.yml`), extend them; do not add a second system.

For a Node repo, default to Husky with lint-staged:
1. Detect the package manager from the lockfile (`pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, else npm).
2. Install `husky lint-staged prettier` as dev dependencies; run `npx husky init` (it adds `"prepare": "husky"`).
3. `.husky/pre-commit` runs `npx lint-staged`, then the project's `typecheck` and `test` scripts. Omit a line whose script does not exist and tell the owner.
4. `.lintstagedrc`: `{ "*": "prettier --ignore-unknown --write" }`.
5. Add a Prettier config only if none exists, using the repo's current style if visible.
6. Verify: the hook file is executable, `npx lint-staged` runs, and a test commit passes through the hook.
7. Commit only these files: "Add pre-commit hooks".

For a non-Node repo, use the `pre-commit` framework or the repo's own tooling with the same shape: format staged files, then typecheck and test.
Keep hooks fast. Never tell anyone to bypass them with `--no-verify`.
