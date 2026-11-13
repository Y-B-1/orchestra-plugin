# Import-boundary lint

Use in Lever mode when the owner asks to enforce module boundaries in a TypeScript repo. This is the lint for imports. The review lens of the same name is `<plugin>/skills/review/references/boundaries.md`.

## The rules
1. Outsiders import only a package's root files (its entry points). Code in subfolders is private.
2. A package's own files import each other freely.
3. Tests import entry points and their own `tests/` fixtures, never any package's internals.
4. A `tests/` folder is importable only from tests.
5. No cycles.
6. Packages are flat: a package never holds another package. Prefer several small entry points over one barrel file.

## Steps
1. Find the package manager, the packages folder and the command that runs typecheck. Ask the owner only if there is no packages folder.
2. The main session installs `dependency-cruiser`. Report BLOCKED if it is missing.
3. Merge the rules below into an existing boundary config. Never overwrite one.
4. Add the lint to the typecheck command.
5. Prove it: pass, then fail on a planted deep import (delete it), then pass.
6. Add a README in the packages folder that states the rules and discourages barrels. Add one line to the repo's rules file that points to it. Add a small example package only if the folder is empty.

## Config (`.dependency-cruiser.cjs`)
Set `ROOT` to the packages folder. `$1` is the package named by `from.path`, so a package reaches its own subfolders and nobody else's.

```js
const ROOT = "src/packages";
const INTERNAL = `^${ROOT}/[^/]+/[^/]+/`; // below a package root
const TESTS = `^${ROOT}/[^/]+/tests/`;
module.exports = {
  forbidden: [
    { name: "outsider-to-internals", severity: "error",
      from: { pathNot: `^${ROOT}/` }, to: { path: INTERNAL } },
    { name: "package-to-other-internals", severity: "error",
      from: { path: `^${ROOT}/([^/]+)/`, pathNot: TESTS },
      to: { path: INTERNAL, pathNot: `^${ROOT}/$1/` } },
    { name: "tests-use-entry-points", severity: "error",
      from: { path: `^${ROOT}/([^/]+)/tests/` },
      to: { path: INTERNAL, pathNot: `^${ROOT}/$1/tests/` } },
    { name: "tests-folder-is-private", severity: "error",
      from: { pathNot: TESTS }, to: { path: TESTS } },
    { name: "no-cycles", severity: "error", from: {}, to: { circular: true } },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsConfig: { fileName: "tsconfig.json" },
  },
};
```

Run it as `npx depcruise src` (or the repo's source folder) beside the typecheck.
