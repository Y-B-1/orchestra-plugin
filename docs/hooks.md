# Hook policy and boundaries

One classifier and two native adapters replace duplicated provider guards. Commands use a supported Python runtime and quoted plugin paths. Hook files are separate to prevent default discovery from loading duplicate handlers.

| Event | Effect | Does not do |
| --- | --- | --- |
| SessionStart | Supply main or worker contract and skill path; on Claude, add the session id for `start --harness-session`; show a pending autonomy morning report | Seed state, repair files, resume, arm autonomy |
| SubagentStart | Supply worker boundaries to agents whose type starts with `orchestra:`; return nothing for any other agent | Veto native startup or authenticate identity |
| PreToolUse | Classify the call and deny covered destructive Git, stash, wholesale staging, protected state/config patches; check recognizable releases and, under autonomy, approval boundaries | Interpret arbitrary scripts, aliases, stdin or all provider tools |
| Stop | Continue only an existing explicitly armed intact ledger, within pass, stall and deadline limits | Start an unrequested loop or continue corrupt state |
| SessionEnd, Claude | Release the run bound to the ending session (see below) | Release on `clear` or `resume`; release a run started without `--harness-session` |
| Interrupt, Codex | Invalidate dispatch and continuation lease | Undo an external action or guarantee every child process stopped |

On Claude the PreToolUse matcher is `Bash|Edit|Write|MultiEdit`. Codex keeps its broad matcher.

## Session end and the lease

`start --harness-session ID` binds the run to the Claude Code session. When that session ends with reason `logout`, `prompt_input_exit`, `other` or an unknown reason, the SessionEnd hook interrupts the run, so a lost lease never locks the next session out. On `clear` and `resume` the process continues under a new id and the run stays armed: the hook records a pending rebind, and the next SessionStart with source `clear`, `resume` or `fork` within 60 seconds binds the run to the new id. Runs started without a harness session are untouched. If the binding is lost anyway, read the actor and lease from `state.json` in the state directory and run `interrupt` with them; the lease is a consistency token, not a secret.

Claude's package has no Interrupt event. On user interruption, the main must stop workers through the harness and run the CLI `interrupt` before further dispatch. Late results cannot advance an interrupted engine run. An OS crash or hook timeout cannot prove that interruption was recorded: inspect actual processes and state before resuming.

## Command classes

The guard sorts every shell command into one class. Classification does not depend on run state; the hook then applies the run state.

| Class | Meaning | No armed run | Armed run | Autonomy active |
| --- | --- | --- | --- | --- |
| `allow` | No rule applies | allow | allow | allow |
| `deny` | Always-deny rule, malformed command or protected path | deny | deny | deny |
| `release` | One release-class command alone (non-force `git push`, `gh pr merge`, `gh release create`, package publish, provider deploy) | allow | needs a current permit | deny |
| `release-multi` | A release-class command inside a multi-command line | allow | deny | deny |
| `boundary` | Deletion (`rm`, `git branch -d`, `git worktree remove` and similar) or local merge, pull, rebase, cherry-pick | allow | allow | deny; a local merge is allowed on a non-default branch |

Always denied whatever the state: force or mirror push, `+refspec`, `--all`, `--tags`, `--delete`, several destinations, `reset --hard`, `clean -f` without `-n`, `branch -D`, wholesale `add`, `commit -a`, wholesale checkout or restore, `switch -f`, and every `git stash` form except `list` and `show`. `git restore --staged` is allowed. Outside an armed run, release-class commands are allowed so ordinary pushes and pull request merges work; inside one, the engine permit applies. A state file that exists but cannot be loaded counts as armed with no permit, and as autonomy-active when its raw flag says so or it is not valid JSON.

Shell parsing removes heredoc bodies and redirections first. A heredoc or here-string body is classified as a script when its consumer is a shell, `source`, `.`, `eval` or `xargs` running a shell, and is scanned for always-deny lines whatever the consumer. Command runners (`xargs`, `find -exec`, `doas`, `stdbuf`, `watch`, `flock`, `sudo`, `env` and similar) are unwrapped so the real command gets its class. Accepted costs: a data heredoc or producer that contains a bare destructive line denies, and a runner that ends in `-c` with no payload denies as malformed.

Accepted limits, because the guard is best effort and not hostile-worker isolation: encoded payloads (base64, `printf` escapes other than `\n`), variable or alias indirection, non-shell interpreters (`python3 -c`, `perl -e`, `node -e`), output process substitution, zsh `=(...)`, and `script` as a runner. Bash writes to protected paths, including the autonomy ledger and the mods marker directory, are not detected. Credential entry is not detected. `gh api` calls and MCP or terminal tools that push or merge are not guarded; using them to get around the guard is forbidden by procedure, not enforced.

A linked worktree of an armed repository gets the same state: the hook resolves the run from the main worktree. A separate clone is a different repository and stays unarmed. Protected paths are the hook and config files of each harness, Orchestra agent files, any `.orchestra` component, the run state directory (except the coordinator's `progress.md`, `standing-orders.md` and `autonomy.md`) and the mods marker directory. `settings.json` is not protected.

## Autonomy boundaries

While `autonomy arm` is active, the hook and the engine enforce the approval boundaries: no release, permit or deploy; no push to any branch; no pull request merge; no deletion; no local merge on the default branch. A denied boundary tells the coordinator to park the card with `park TASK --reason ...` and continue with other cards. Release permits stay unavailable until the user disarms. Stop never arms autonomy by itself.

## Mods on Claude Code

The plugin registers a function-hook module (`hooks/mods.json`, loaded beside `hooks/claude.json`). It needs a Claude Code build that enables function hooks (`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`) and exposes the `$` APIs the module uses; tested on Claude Code 2.1.289 (CLI) and 2.1.286 (embedded in Desktop, with that variable set). There is no version floor. The module has no explicit API check. If a needed API is missing, session start fails, the guard stays not ready and guarded calls fall back to the Python hooks; if the module fails to load, the Python hooks guard every call. Both are the safe direction.

When active, the module classifies Bash, Edit, Write and MultiEdit calls in process with a TypeScript port of the same rules and writes a heartbeat marker under `${XDG_STATE_HOME:-$HOME/.local/state}/orchestra/mods/`. A fresh marker whose rules digest matches lets the Python PreToolUse hook return at once; a missing, stale or mismatched marker makes Python guard in full. Release, release-multi and boundary calls are always delegated to Python, because only the engine knows the run, permits and autonomy. The module also adds `/orchestra-board`, `/orchestra-autonomy on|off|status`, verdict and stop toasts and an autonomy status band, and appends the run's standing orders to briefs for `orchestra:` agents. These are display and convenience only. Without mods everything above still works through the Python hooks and the CLI.

## Release hooks

Release hooks check existing permits; a tool request cannot create one. Structured release execution independently checks configured authority, exact command, current final reviews and required gates. Known Git pushes need exactly four argv elements: the engine's resolved Git executable, push, the configured remote and one refspec. The source must resolve to the reviewed full HEAD. Wrappers and global/push options are rejected because they can change repository or destination context. Default policy names no remote, deployment, database operation or release command. Required missing scanners block; optional missing scanners report unavailable.

Workers retain documentation/browser tools and relevant state reads. Native profiles disable nested agent tools; prompts prohibit coordinator writes. Caller-supplied actor names and environment role markers are advisory consistency inputs. They do not authenticate a worker, and arbitrary interpreter writes are outside the shell classifier. Use host sandbox, remote branch protections and tool policies for stronger isolation.

Opening a session never installs old charter healers, stale-state rewrites, fixed product ports, relay forwarding, automatic rollback or source deployment recipes. ActionNotch and Orca integrations remain separate.

Codex does not automatically trust bundled hooks. Review and trust the current definition in the host interface; updates can need another review. Installer code never edits trust or uses a trust bypass. [Codex hooks](https://developers.openai.com/codex/hooks), [plugin hook packaging](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks).
