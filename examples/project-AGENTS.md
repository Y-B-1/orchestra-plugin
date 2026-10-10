# Acme web app

<!-- Example project charter. Save it as AGENTS.md at the repository root.
     Claude Code loads AGENTS.md when the project has no CLAUDE.md.
     The Orchestra coordinator copies the "Standing orders" section verbatim into every worker brief,
     so keep binding rules there and keep them checkable. Replace every name, path and command. -->

Customer-facing web app: a TypeScript API in `api/` and a React client in `web/`. Read `docs/AGENT-MEMORY.md` before you start; it holds current state and open decisions. Domain terms are in `CONTEXT.md`.

## Commands

| Purpose | Command |
|---|---|
| Install | `npm ci` |
| Fast check per edit | `npm run lint && npm run typecheck` |
| Unit tests for one package | `npm test -w api` or `npm test -w web` |
| End-to-end, one spec | `PORT=4100 npm run e2e -- <spec>` |
| Impact set before merge | `npm run test:changed` |
| Full suite (owner request only) | `npm run test:all` |

Each worker that runs end-to-end tests takes its own port from 4100 to 4199.

## Standing orders

These rules bind every agent and every worker, including subagents.

1. Edit only the paths your card owns. Preserve edits made by others.
2. Never edit `api/migrations/` once a migration is merged. Add a new migration instead.
3. Never commit secrets. Configuration comes from `.env.local`, which Git ignores.
4. Commit each working iteration with explicit paths. Never stage wholesale, stash, force push or reset hard.
5. New behavior and bug fixes start with a failing test. Tests assert behavior, never the mock.
6. Public API changes update `docs/api.md` in the same commit.
7. Release is not authorized for agents. The owner merges to `main` and deploys.

## Ownership and parallel work

- `api/` and `web/` are independent units. Two builders can work on them at the same time in separate worktrees.
- `packages/shared/` is shared. Only one card owns it at a time; dependent cards wait until that card is accepted.

## Review

- Every pull request gets one independent pre-PR review of the frozen candidate.
- A diff that touches a sensitive path gets the `security` lens. The default list covers `**/auth/**`, `**/security/**`, `**/*secret*`, `**/migrations/**` and a few others. To cover payments too, this project passes `start --policy` a JSON file whose `sensitive_paths` repeats the default list and adds `api/payments/**`; the key replaces the default, it does not extend it.

## Memory

Update `docs/AGENT-MEMORY.md` in the commit that closes a batch, then prune entries that are done. Personal preferences belong in the user's global file, not here.
