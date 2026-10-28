# Live check

`python3 scripts/live-check.py` runs Orchestra's hooks in three real headless Claude Code sessions. Unit tests call the hook functions directly; this check proves that Claude Code loads the plugin and runs the hooks. Run it before a release. It uses haiku and costs a few cents. `scripts/check.sh` never runs it.

Each scenario creates a scratch Git repository with a bare `origin` and runs `claude -p` with `--setting-sources ""`, `--strict-mcp-config`, `--permission-mode bypassPermissions`, `--plugin-dir plugins/orchestra`, `--model haiku` and `--output-format stream-json --verbose`. The environment holds only `HOME`, `USER`, `PATH`, `SHELL`, `LANG`, `TMPDIR` and `TERM`, so your own settings, hooks and MCP servers do not load.

| Scenario | Passes when |
| --- | --- |
| init | The init event lists the skill `orchestra:orchestra`, the five `orchestra:*` agents and the command `orchestra:goal`, and the SessionStart hook output names `.git/orchestra/asks.md` |
| guard | `git push origin main` is denied with the Orchestra reason and `origin/main` does not move; `git push -u origin feature` runs and creates the branch on `origin` |
| goal | `/orchestra:goal` runs with one open ask in the ledger, and the Stop hook blocks at least once |

The script prints PASS or FAIL per scenario and exits 0 only when all three pass. A failed scenario keeps its event stream in the temporary directory and prints the path.

Claude Code 2.1.306 emits no `hook_response` event for the Stop hook in headless runs. The goal scenario therefore also accepts the `Stop hook feedback` message that Claude Code feeds back to the session when the hook blocks.
