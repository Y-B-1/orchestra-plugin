# Orchestra 2.0.0 release notes

Orchestra 2.0.0 consolidates ten worker roles into six, rewrites the skills, repairs the guard, adds a Claude Code function-hook module and an autonomous overnight mode, and trims the engine. It is a breaking release.

## Breaking changes

- Roles. The engine accepts only the 2.0 role names below. A card or dispatch that names a 1.0.1 role is rejected as an unavailable role. A live 1.0.1 run cannot continue, and `start --new-run` cannot clear it after the upgrade. Before upgrading, end it with 1.0.1 still installed (see Install path from 1.0.1). A finished or interrupted 1.0.1 run only needs `start --new-run`.
- Removed commands: `route`, `review-groups` and `audit-policy`. Calling one exits with an unknown-command error. The coordinator chooses lanes, groups reported cards and picks audit axes by hand, following the skill references.
- Removed policy keys: `reserved_ports` and `denied_tools`. An old policy file that still carries them loads unchanged.
- `status` and `board` no longer print the lease. `start` prints it once.
- `autonomy` changed from `autonomy LEDGER --max-passes N --max-stalls N` to `autonomy arm|disarm|status`.
- The autonomy progress measure is the set of newly accepted cards, not a digest of cards, artifact and gates.
- A live run is invalidated only when a role or mode is added, removed or renamed. Editing a skill file no longer invalidates it.
- The Claude orchestrator agent no longer pins a model or effort: it follows your picker.
- Claude `PreToolUse` now matches only `Bash|Edit|Write|MultiEdit`.

## Role mapping

| v1 role | v2 role and mode |
| --- | --- |
| orchestrator | orchestrator / main |
| investigator, investigator-code | investigator / docs, code |
| founder-mind (design) | designer-planner / product |
| founder-mind (audit) | critic / surface |
| designer-planner | designer-planner / design, plan |
| red-teamer | critic / requirements, feasibility, scope, judge |
| auditor | critic / spec, standards, ledger |
| builder | builder / implementation, frontend, sensitive, mechanical |
| builder-repair | builder / repair |
| code-reviewer, code-reviewer-checkpoint | code-reviewer / final, checkpoint |
| gatekeeper | operator / gate |
| janitor | operator / cleanup |
| releaser | operator / release |

New builder mode `cleanup` applies a lean-and-simplify pass at the end of a run on confirmed findings from the final review. Each worker role has one skill built from the shared worker contract plus one mode file. Models are in [docs/models.md](models.md).

## New commands and features

- `artifact --tasks ID[,ID]` prints evidence scoped to the covered cards' reserved files plus HEAD.
- `autonomy arm|disarm|status`, `park TASK --reason TEXT` and `unpark TASK`: autonomous overnight mode with a ledger, pass and stall caps, a deadline, hard approval boundaries and a morning report.
- `where` prints the repository, state directory and whether standing orders exist, without the lease.
- `start --harness-session ID` and a Claude `SessionEnd` hook release a run when its session ends, with `clear` and `resume` rebinding instead. This fixes the lockout after a lost session.
- `required_review_categories` can narrow the seven final-review categories to a non-empty subset.
- Claude Code function-hook module: in-process guard with a heartbeat marker, `/orchestra-board`, `/orchestra-autonomy`, toasts and a status band. It needs function hooks enabled (`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`) and the APIs it uses; with either missing, the Python hooks guard instead.
- Third-party notices for the MIT sources the skills draw on: `plugins/orchestra/THIRD-PARTY-NOTICES`.

## Guard changes

- Outside an armed run, release-class commands are allowed: non-force push of one branch or tag, `gh pr merge`, `gh release create`, package publish and provider deploys. Inside an armed run the permit applies; with autonomy active they are denied. A state file that cannot be loaded fails closed (armed, no permit), unless it parses with `session` null or `session.active` false: that ended run is unarmed.
- Always denied, armed or not: force and mirror push, `+refspec`, `--all`, `--tags`, `--delete`, several destinations, `reset --hard`, `clean -f`, `branch -D`, wholesale `add`, `commit -a`, wholesale checkout or restore, `switch -f`.
- `git stash list` and `git stash show` are allowed; other stash forms are denied. `git restore --staged` is allowed.
- Heredoc and here-string bodies no longer raise a quoting error. They are classified as scripts when fed to a shell, `source`, `.`, `eval` or `xargs` running a shell, and always scanned for always-deny lines. Command runners (`xargs`, `find -exec`, `doas`, `stdbuf`, `watch`, `flock`) are unwrapped.
- New command classes: `allow`, `deny`, `release`, `release-multi` and `boundary` (deletion or local merge). Boundaries matter only while autonomy is active.
- `az` is release-class only for `deployment ... create` and `repos pr update ... --status completed`. `settings.json` is no longer a protected path. A linked worktree of an armed repository shares the main worktree's run state.
- One guard rules table and one test corpus keep the Python and TypeScript guards in step.

## Install path from 1.0.1

A marketplace name is unique, so uninstall and remove the 1.0.1 marketplace before adding the new one, in a plain terminal:

```sh
claude plugin uninstall orchestra@orchestra-distribution
claude plugin marketplace remove orchestra-distribution
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
claude plugin list
```

Before the uninstall, deal with any run left active. A 1.0.1 run that was finished or interrupted leaves the repository unarmed under 2.0.0; plain `start` and `status` say to run `start --new-run`, which archives the old state. A run still active must be ended with 1.0.1 first, from its repository, with 1.0.1 still installed. Claude Code: `python3.11 ~/.claude/plugins/cache/orchestra-distribution/orchestra/1.0.1/scripts/orchestra.py --lease LEASE interrupt` (or `finish`). Codex only: `python3.11 ~/.codex/plugins/cache/orchestra-distribution/orchestra/1.0.1/scripts/orchestra.py --lease LEASE interrupt`. LEASE is the value `start` printed; if you lost it, the same script's `status` prints the state and the lease is `session.lease`. If you already upgraded with a run active, move that run's `state.json` out of its state directory by hand; the repository is then unarmed. `orchestra.py where` from the repository prints the state directory. It is `$ORCHESTRA_STATE_DIR` when set, otherwise `${XDG_STATE_HOME:-~/.local/state}/orchestra/<id>`, where `<id>` is the first 24 hex characters of the SHA-256 of the repository's absolute path.

Restart Claude Code and start a new run. For Codex, update the clone first, because `install-profiles` installs the profiles of the clone it runs from:

```sh
codex plugin marketplace upgrade orchestra-distribution
codex plugin remove orchestra@orchestra-distribution
codex plugin add orchestra@orchestra-distribution
git -C orchestra-plugin pull --ff-only
python3.11 orchestra-plugin/plugins/orchestra/scripts/orchestra.py install-profiles
```

Review and trust the hook definition again in Codex if it asks. See the [README](../README.md#install).

## Known limits

- The guard is best effort and not hostile-worker isolation. It does not see encoded payloads (base64, `printf` escapes other than `\n`), variable or alias indirection (`G=git; $G reset --hard`), non-shell interpreters (`python3 -c`, `perl -e`, `node -e`), output process substitution, zsh `=(...)`, a zsh redirect operand that expands to several words, or `script` as a runner.
- Accepted false positives: a data heredoc or producer containing a bare destructive line denies, as in 1.0.1; `eval` with a heredoc operator and a runner ending in `-c` with no payload deny as malformed.
- Mods are unsandboxed. Bash writes to protected paths, including the mods marker directory and the autonomy ledger, are not detected. Credential entry is not detected.
- `gh api` calls and MCP or terminal tools that push or merge are not guarded. Using them to get around the guard is forbidden by procedure, not enforced.
- Caller-supplied actor names, leases and role markers are consistency checks, not authentication.
- Hook trust is never written by the installer. Trusted automatic startup, live discovery and the interactive mods behavior are user checks, not established by the unit suite.
- 2.0.0 has no automatic recovery for a run left active across the upgrade; use the manual `state.json` move in Install path from 1.0.1.
- Edit or Write through a symlink into the protected marker or state directory is not caught by the mod's lexical path check; the Python `resolve()` check runs only when the mod is not live.
- Classifying a long chain of here-strings is quadratic in its length.
- `docs/models.md` is a hand copy of `config/models.json`; keep them in step by hand.
- `plugins/orchestra/hooks/mod/fixtures/o17-cases.ts` duplicates corpus cases.
- Windows is not supported by the POSIX locking core; use WSL.
