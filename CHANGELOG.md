# Changelog

Release 2.0.0 is described in docs/RELEASE-NOTES-2.0.0.md.

## 2.6.5 — 2026-10-15

- **Autonomy, pull request push:** `autonomy arm` records where each remote pushes to (`git remote get-url --push --all`, which applies `pushurl`, `insteadOf` and `pushInsteadOf`; a remote with more than one push URL gets no pull request push), and a pull request push is refused when that answer differs at push time. A changed remote URL or rewrite can no longer redirect an approved push, whichever setting or route caused it; this backs up the guarded-key list instead of relying on it. A state armed before this release has no record, so re-arm.

## 2.6.4 — 2026-10-15

- **Docs only:** `docs/BUILD-LEDGER.md` and `docs/VALIDATION.md` record the live checks run against the published 2.6.3 release: install from GitHub, the `deadline` stop, `clear` and `resume` rebinding, and the large route with one repair ending in `hold`. No plugin code changed.

## 2.6.3 — 2026-10-14

- **Autonomy, default branch:** `autonomy arm` now asks every remote for its current default branch, even when one is already recorded, and stores the answers in the run state (`remote_defaults`). The pull request push guard checks against those answers instead of the local `refs/remotes/<remote>/HEAD`, which could be stale after the remote changed its default. A remote that does not answer gets no pull request push until autonomy is armed again.
- **Autonomy, arming:** the remotes are asked before the armed state is written, so an `arm` interrupted during that step leaves autonomy off.
- **`pr URL`:** requires an http(s) URL with a host; `https:///pull/1` and similar are refused.
- **Releases:** `.github/workflows/release.yml` publishes a GitHub release for the plugin version, with the archives and their checksums. Push the tag `v<version>`, or run the workflow by hand from main, which creates the tag itself. It refuses a commit that is not on main, a tag that does not match `plugin.json` and a missing `docs/release-notes/v<version>.md`.
- **Gates:** processes a gate leaves running in its own process group are stopped when it exits; one that starts a new session or group is not tracked.
- **Guards:** a run cannot set or unset the Git configuration that routes or rewrites a push (aliases, `remote.*`, `url.*`, `push.*`, includes, `submodule.*`, `http.*`, `credential*`, `core.sshCommand`, `core.gitProxy`, `core.hooksPath`), and unrecognized `git config` forms and `git remote add`, `set-url`, `rename` and `remove` are refused; reading config and setting ordinary keys still work.
- **Mod markers:** a session start deletes the heartbeat markers of sessions that ended more than a day ago.
- **Permits:** documented that a release permit stays valid until the artifact changes or the session ends.
- **CI:** `.github/workflows/ci.yml` runs the generator check and the test suite on Python 3.11 and 3.13, and the strict plugin and marketplace validation plus the mod tests, on every pull request and on main. It lives in the repository, not in the installed plugin, and the release archive leaves it out.

## 2.6.2 — 2026-10-14

- **Pull requests in the brief:** `orchestra.py pr URL` (lease) records a pull request the run opened; every run brief lists it under Needs you as "review and merge pull request URL". The autonomy instructions record the PR this way instead of a free-form `progress.md` line.
- **Validation:** a full unattended autonomy run, from the first message to `complete`, is recorded in BUILD-LEDGER.md and VALIDATION.md.

## 2.6.1 — 2026-10-14

- **Autonomy:** `autonomy arm` records each remote's default branch where it is missing (`git remote set-head <remote> --auto`, outside the state lock, 20 s per remote) and reports it as `remote_heads` in the preconditions. A remote it cannot reach is reported and arming still succeeds; pull request pushes to that remote stay refused until its default branch is known. No manual `set-head` step before arming.

## 2.6.0 — 2026-10-14

- **Autonomy loop:** the Stop hook continues a turn only when the coordinator can act now (a ready or reported card, an open final finding, a held chain owed its final review). Running workers alone let the turn end; the harness wakes the session when one finishes. Once every card is accepted it continues into the final review, gates and pull request. A continuation is never sent twice for an unchanged progress signature: that turn ends as a stall, and a stall with no worker running stops the run with the new reason `stalled` (nothing would wake it). Before, every Stop while workers ran re-sent the same prompt.
- **Relaunch removed:** `orchestra.py relaunch`, `autonomy arm --relaunch`, `autonomy settle` and `config/relaunch-prompt.md`. Passes could only run foreground workers, and the context-ceiling rule had no signal. A 2.5 state carrying the flag loads, and its autonomy is dropped when a new session opens over the inactive run; re-arm in a live session.
- **Guards: ask instead of block:** during an interactive run, a release action (`git push`, `gh pr merge`, `gh release create`, package publish, deploy) runs with a current engine permit and otherwise raises Claude Code's approval prompt, instead of being denied. A release inside a multi-command line asks too. Because a mod `tool.call` hook cannot ask, the Python hook no longer takes the fresh-marker shortcut for release commands.
- **Guards: autonomy opens pull requests:** under autonomy, a plain push of one feature branch (not the remote's default branch, `main` or `master`) is allowed, and `gh pr create` already was. Merge, other releases, default-branch pushes and deletion stay denied and park the card; the owner merges after the run. The ledger's fixed Push line is now `- Push: push only a feature branch for a pull request; never the default branch.`; a 2.5 ledger's `no push to any branch` line still arms.
- **Autonomy cleanup:** under autonomy the coordinator may delete a branch (`git branch -d|-D`, `git push <remote> --delete`) or remove a linked worktree (`git worktree remove` without `--force`, `git worktree prune`) when the branch is provably merged into the default branch. Each runs as a plain single command. `rm` and every other deletion stay denied.
- **Autonomy pull request push tightened:** only `git push [-u|--set-upstream] <remote> <refspec>` with a configured remote name (no `remote.<name>.push` or `pushurl`), a local branch as source and one destination branch other than the remote's default branch, `main` or `master`, compared case-insensitively. The remote's default branch must be known locally (`git remote set-head <remote> --auto`).
- **Release classification:** `gh api` calls that mention merge (a `pulls/N/merge` call or a `mergePullRequest` mutation), a `gh api graphql` call with a mutation or a request body the guard cannot read (`--input`, a `=@file` field), and `cargo publish` are release actions.
- **Hooks:** the PreToolUse timeout is 30 seconds. Without Python 3.11 or later, `run-hook.sh` fails PreToolUse closed (exit 2) and only warns on every other event; it probes each candidate interpreter, so a broken pyenv shim is skipped. A relative `XDG_STATE_HOME` is ignored.
- **Release archive:** `scripts/build_release.py` leaves out tests and development files. Its private-content scan also catches Linux home paths, `github_pat_`, Slack `xox` tokens and AWS `AKIA` keys.
- **Engine hardening:** task JSON can no longer set engine-owned fields; a stale review with findings blocks `accept`; `start --policy` validates the file; CLI errors exit 2 with JSON. A 2.5 state armed with `--relaunch` no longer re-arms on `start`.
- **Docs:** the turn ends while background workers run; open the pull request before `complete`; fix re-review briefs need no `Lens:` line; the standards lens uses `code-reviewer-standards`; ending the session ends autonomy only for a `--harness-session` run; README uninstall steps.
- **README:** rewritten end to end: install, the run from first message to completion, one roles table with subtypes, the guard modes, autonomy, commands and condensed upgrade notes.
- **Context:** the triage escalation no longer cites a percentage of the window. The README recommends `autoCompactWindow` in the user's Claude Code settings.

## 2.5.1 — 2026-10-10

- **Engine:** a run state whose session carries `size` never loads under the 2.3 policy hash. Before, `binds()` refused only a session with `items`. The two task-size checks share one constant, `CARD_SIZES`.
- **Examples:** `examples/global-CLAUDE.md` (a user-level `~/.claude/CLAUDE.md` that routes through Orchestra) and `examples/project-AGENTS.md` (a project charter whose standing orders Orchestra pastes into every brief).

## 2.5.0 — 2026-10-09

Route by diff size instead of item count. The design is `docs/DESIGN-v2.5.md` (owner decisions D1 to D5), the contract is `docs/PLAN-v2.5.md` section 2.

- **Size tiers (D1):** `start --size tiny|medium [--asks N]` is required for a new run. Tiny is up to 50 changed lines (inline edit, no alignment; a tiny builder card needs `dispatch --helper REASON`), medium up to 400 (grill inline, then every unit inline in sequence; the medium benchmark showed a worker's fixed cost exceeds a medium unit's inline time). Large runs 2+ units through Workflow builders, and the coordinator starts its own inline card in the same turn. `--asks` counts separately stated asks; the tier is the largest ask and the budget is the guide times the count.
- **Large only by escalation:** `route --size large --reason TEXT`, or `start --size large --owner-request` when the owner asks for a map. A designer-planner plan card needs a large run or an owner request.
- **Size check (D2):** the new read-only `prepr` command compares the diff with the budget and prints a warning; it never blocks.
- **Reviewer by summed diff (D3):** `prepr` names the pre-PR reviewer: Sonnet 5.5 (`code-reviewer-medium`) up to 400 changed lines, one card with `Lens: combined`; Opus 5.5 with one card per lens above 400.
- **Wayfinder (D4, D5):** `references/wayfinder.md` maps large work as decision tickets in `docs/maps/<name>.md`; research tickets run together as investigator cards. Derived from mattpocock/skills at 49dd158d1076 (third pin, credited).
- **Engine gaps:** `gate --timeout SECONDS` overrides the policy timeout for one run. A reported card takes a replacement report from the same worker until accept or a review covers it, so a wrong report no longer needs park and unpark. A builder report needs a nonempty `ARTIFACT:` line, so a report cannot be accepted with no commit named.
- **Upgrade:** a 2.4 run loads under 2.5 and keeps item routing; `start --items` is refused (README, Upgrade from 2.4 to 2.5).

## 2.4.0 — 2026-10-08

Inline-first routing, builder self-review and one review before the PR. The decisions are `docs/PLAN-v2.4.md` section 1 (S1–S11), the contract is section 2.

- **Model matrix (S1, S2):** Haiku 5.5 high for mechanical and cleanup builders, operator and code discovery; Opus 5.5 only for critic (high), final reviewer and builder repair (medium).
- **Routing (S3, S11):** `start --items N` is required for a new run; 1 to 5 items run inline (`dispatch --helper REASON` for a helper builder), 6 or more go through a designer-planner plan card and Workflow builders. `route` changes the route mid-run.
- **Self-review (S6):** a builder report carries one `SELF_REVIEW:` JSON line with its checks and criteria; the engine accepts a builder card on it while the artifact is current.
- **One review before the PR (S4, S5, S7):** checkpoint review, waves, gates between waves, `supersede` and the `code-reviewer-checkpoint` agent are removed. Only the pre-PR review and one fix re-review are recorded; a chain still blocked after that is held. Lenses come from the diff: security on `sensitive_paths`, standards above `standards_min_lines`.
- **Guards (S9, S10):** during a run the main session may start only `orchestra:*` agents (denied also when the run state cannot be loaded), and shell, edit and agent calls from any other agent, including agents a Workflow starts, are denied (file reads are not guarded). Reviewers and critics cite a current gate receipt instead of rerunning a test suite.
- **Upgrade:** a 2.3 run loads under 2.4 with 2.3 routing; its gate and review receipts go stale (README, Upgrade from 2.3 to 2.4).

## 2.3.0 — 2026-10-06

Four small items folded from mattpocock/skills at 2b47ffcf2385 (second pin; credited in `plugins/orchestra/THIRD-PARTY-NOTICES`).

- **Strategic track:** the coordinator works a tactical track (finish the task) and a strategic track (change the environment so the next task goes better: a lint rule, a constrained API, a standards file or a check, not more instructions). `coordination.md`, section Two tracks.
- **No workarounds:** a deviation from project convention is fixed, as its own card, before feature work builds on it.
- **Bug-lane retro:** after an accepted repair, name the missing check or seam that would have caught the bug and route adding it.
- **Handoff directory:** `handoff.md` names the temporary directory: `$TMPDIR`, else `/tmp` (`%TEMP%` on Windows).

## 2.2.0 — 2026-10-05

The full change set is `docs/SPEC-v2.2.md` section 5; each item below names its section.

- **Wave review and repair-diff check (5.1):** one checkpoint review per wave over its reported tickets; a repair is checked against its own diff before the chain tip is accepted (`repair_check`, `supersede`, wave labels in `status`).
- **Repair ladder ending in hold (5.2, 5.3):** a builder gets one repair; a chain still blocked after it is held (`hold`), its work stays in place, the held log records it and the run continues. Held dependencies count as satisfied.
- **Gates between waves (5.4, 5.11):** gate receipts are recorded once and reused; a repeated gate needs `gate --again`; boundary gate argv is refused.
- **Final phase (5.5):** three parallel lenses (correctness and security on Opus 5.5 high, standards on the new Sonnet 5.5 medium `code-reviewer-standards` variant). Final receipts attribute findings to chain tips and must address every held tip. The final repair loop has no round cap.
- **Materiality (5.6):** review reports separate blocking `findings` from `issues`; work with no real impact, or under about 20% impact on otherwise-correct work, is a note, never a failure.
- **Out-of-scope triage and findings ledger (5.7, 5.12):** out-of-scope defects never change a verdict; they are triaged inline, as a card or in the brief.
- **Autonomy without caps (5.8):** the deadline is the only limit; `max_passes` and `max_stalls` from 2.1 ledgers are recorded but not enforced. Stalls are detected by signature. The status band reads "pass N". A ledger `Release:` line pre-authorizes one exact remote and target pair.
- **Run brief (5.9):** every end path appends one `## Run brief` to `progress.md`; `brief` prints it.
- **Relaunch harness (5.10):** `orchestra.py relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]` runs fresh-context passes until `complete`, `deadline` or a stop, with `settle` before each pass and a pass session nonce. A signal disarms autonomy without taking the state lock in the handler.
- **Briefs carry exact keep and remove lists (5.13).**
- **Guard (5.14, 5.15, 5.16):** forced deletion of a branch that is provably merged into the default branch is allowed (local and remote; the remote push URL must equal its fetch URL; default refs and the branch name are matched exactly, case included). Raw ref deletion through `git update-ref` is denied. Abbreviated long options are read as git reads them; `commit --amend` is denied. Hook state reads wait at most 2 s; a busy lock or a removed session directory denies only the delegated classes, with a reason. The mod's fail-closed message names its failure class, and `delegate` spawns from the plugin root. The chained-command failure reproduced at the mod seam (missing session directory); the fix ships here.
- **Engine (5.17):** read-only reviews no longer collide with the cards they review.
- **Mixed versions on one active run (section 8):** a 2.1 engine reading 2.2 state rejects any `held` card and an armed autonomy without `max_passes`, and the 2.1 hooks then fail closed for that run. End every 2.1 session before the first `hold` or before arming autonomy under 2.2.

## 2.1.0 — 2026-10-05

- Claude-native only. Removed the Codex package (`plugins/orchestra-codex`), `.agents`, the Codex manifest and hook file, the generated worker profiles, `install-profiles` and `uninstall-profiles`, and every Codex path in the engine, hooks and generator. `config/models.json` keeps only the claude profile. Claude roles, models and efforts are unchanged; `agents/*.md` are byte-identical to 2.0.1.
- Stricter Git guard, in both the Python guard and the TypeScript mod, kept in parity by the shared corpus: every `git stash` form is denied (including `list` and `show`); wholesale `git add` is denied (`-A`, `-u`, `--all`, `--update`, `--no-ignore-removal`, short clusters with `A` or `u`, and the pathspecs `.`, `./`, `..`, `../`, `:/`, `:/.` and `*`); `git commit -a`, `--all` and clusters with `a` are denied. Commit messages that merely mention these words stay allowed.
- Docs and skill references rewritten for Claude only. Historical records are unchanged.

## 2.0.1 — 2026-10-04

- Claude `PreToolUse` matcher now includes `Agent` and `Task` (`Bash|Edit|Write|MultiEdit|Agent|Task`), so workers cannot delegate in Claude Code. This supersedes the 2.0.0 note that the matcher covered only `Bash|Edit|Write|MultiEdit`.
- Test: `_MOD_TOOLS` in `orchestra_core/hooks.py` must equal `GUARDED` in `hooks/mod/orchestra.ts`, so the two lists cannot drift apart.
