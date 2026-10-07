Source: derived from obra/superpowers@8ca22dba9a94 skills/using-git-worktrees/SKILL.md skills/finishing-a-development-branch/SKILL.md skills/diagnosing-superpowers/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/retro/SKILL.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-retrospective/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-operate/references/cleanup.md

# Operator: cleanup mode

Two jobs, both read-only until the coordinator assigns a removal: a hygiene pass over worktrees, branches and temporary state, and a retro over finished work. The output is a proposal with evidence. You remove nothing on your own.

## Hygiene pass

Inspect the directory, not the refs. A merged branch says nothing about edits left uncommitted after the commit.

1. List what exists: `git worktree list`, `git branch -vv`, and for each worktree the brief names, `git -C <worktree> status --porcelain -uall`.
2. Tell a linked worktree from a plain checkout: compare `git rev-parse --git-dir` with `--git-common-dir`. Differing values with a non-empty `git rev-parse --show-superproject-working-tree` mean a submodule, not a worktree.
3. For each branch, list commits that its base branch lacks: `git log <base>..<branch> --oneline`.
4. Check liveness: a live process, and the transcript's last modification time. A journal line records what started, not what still runs. Check this before you call anything stale.
5. Check temporary files, generated-file drift (the project's own drift check), and whether the project memory file carries this run's facts.

Ownership rules for the proposal:

- Propose removal only for worktrees the dispatching coordinator created for this unit. Leave host-created and other workers' worktrees alone.
- A dirty or untracked worktree is not disposable. Show the file list and the three ways out: commit to a named branch, move the files out, or delete them as unrecoverable. The coordinator or user picks.
- Commit to a named branch to preserve work. A detached HEAD is not preservation; garbage collection eats it.
- Never stash: all worktrees share one ref store, so a stash is repo-wide.
- Never `--force` a refused removal. Never rewrite history another worker may hold.
- Tracked memory changes land before the final gates. A later edit voids earlier evidence.

Return the proposal: each item, its evidence (command, exit code, log path), the action proposed and who must approve it. Removal runs only under a coordinator assignment that names the item.

## Retro

The brief carries the problem statement and the session paths. If either is missing, stop with `STATUS: BLOCKED`. You work through every dimension.

Rules for reading sessions:

- Session files are read-only. Never modify, move or delete one.
- Measure first: `wc -lc <file>`, then find long lines. A single record can exceed a megabyte. Take line numbers and counts before content, extract fields from named lines, and narrow any result over 500 characters.
- Only human-typed prompts are the user's words. Hook output, reminders and tool results are not.
- Every finding cites `path:line`, a commit or a log. No citation, no finding. Every number comes from the transcript or a command you ran.
- Treat a sub-report from any source as unverified until you reopen its source.

Check these dimensions:

- skill timeline: which skills fired, and where a matching request got none;
- plan adherence: steps skipped, reordered, silently changed or invented;
- repeated work: reads, edits, commands or dispatches repeated with nothing changed between them;
- stumbles: failures, retries, reverts, human corrections, denials;
- quality evidence: completion claims with no command output behind them, and commits that claim work no call performed;
- request conflicts: instructions that contradict each other or the standing orders;
- cost and time: the largest turns and tool results, with numbers.

Then look for improvements to the agent's environment:

- navigation: slow searches that a pointer in a steering file would fix;
- automated checks: a mistake a lint, type or test check would have caught, or a check that exists but is not wired;
- coding standards: a mechanical violation gets a deterministic check; only a judgement call becomes a written standard;
- instruction-file bloat: rules that moved to checks, and rules that change no behavior;
- tool economy: expensive calls that could be cheaper;
- information access: facts the agent could not reach.

For each finding, propose a check, not another sentence of instructions. Give each action item an owner and the finding it traces to. Mark whether last retro's action items landed, with the source that shows it, or "no evidence found". Proposals are not applied by you.
