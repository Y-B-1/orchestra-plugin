# Changelog

Release 2.0.0 is described in docs/RELEASE-NOTES-2.0.0.md.

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
- **Guard (5.14, 5.15, 5.16):** forced deletion of a branch that is provably merged into the default branch is allowed (local and remote; the remote push URL must equal its fetch URL; default refs are matched exactly). Raw ref deletion through `git update-ref` is denied. Abbreviated long options are read as git reads them; `commit --amend` is denied. Hook state reads wait at most 2 s; a busy lock or a removed session directory denies only the delegated classes, with a reason. The mod's fail-closed message names its failure class, and `delegate` spawns from the plugin root. The chained-command failure reproduced at the mod seam (missing session directory); the fix ships here.
- **Engine (5.17):** read-only reviews no longer collide with the cards they review.
- **Mixed versions on one active run (section 8):** a 2.1 engine reading 2.2 state rejects any `held` card and an armed autonomy without `max_passes`, and the 2.1 hooks then fail closed for that run. End every 2.1 session before the first `hold` or before arming autonomy under 2.2.

## 2.1.0 — 2026-10-05

- Claude-native only. Removed the Codex package (`plugins/orchestra-codex`), `.agents`, the Codex manifest and hook file, the generated worker profiles, `install-profiles` and `uninstall-profiles`, and every Codex path in the engine, hooks and generator. `config/models.json` keeps only the claude profile. Claude roles, models and efforts are unchanged; `agents/*.md` are byte-identical to 2.0.1.
- Stricter Git guard, in both the Python guard and the TypeScript mod, kept in parity by the shared corpus: every `git stash` form is denied (including `list` and `show`); wholesale `git add` is denied (`-A`, `-u`, `--all`, `--update`, `--no-ignore-removal`, short clusters with `A` or `u`, and the pathspecs `.`, `./`, `..`, `../`, `:/`, `:/.` and `*`); `git commit -a`, `--all` and clusters with `a` are denied. Commit messages that merely mention these words stay allowed.
- Docs and skill references rewritten for Claude only. Historical records are unchanged.

## 2.0.1 — 2026-10-04

- Claude `PreToolUse` matcher now includes `Agent` and `Task` (`Bash|Edit|Write|MultiEdit|Agent|Task`), so workers cannot delegate in Claude Code. This supersedes the 2.0.0 note that the matcher covered only `Bash|Edit|Write|MultiEdit`.
- Test: `_MOD_TOOLS` in `orchestra_core/hooks.py` must equal `GUARDED` in `hooks/mod/orchestra.ts`, so the two lists cannot drift apart.
