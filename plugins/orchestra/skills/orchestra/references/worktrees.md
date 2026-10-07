Source: derived from obra/superpowers@8ca22dba9a94 skills/using-git-worktrees/SKILL.md skills/finishing-a-development-branch/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/worktrees.md

# Worktrees

A worktree buys isolation and nothing else. Use the fewest that keep writers apart:

- Work whose files intersect shares one worktree.
- A single writer, or writers in sequence, use none: the main tree.
- Concurrent writers on disjoint files get one worktree per group.
- A read-only worker uses the main tree.

Group the work into PRs first (the inline session for 1 to 5 items, the designer-planner for 6 or more); a worktree follows a group, never a ticket.

## Create

1. Detect existing isolation first: compare the git dir with the common dir. Inside a linked worktree, reuse it. In a submodule, stop and ask.
2. Prefer the host's native isolation tool; otherwise run `git worktree add` on a named branch.
3. Confirm the worktree directory is ignored by git.
4. Set up the project and run the scoped baseline checks before any edit.

A worktree serves one group of work. The dispatcher who created it removes it when that group merges.

## Share nothing

Never stash: all worktrees share one ref store, so a stash is repo-wide.

Commit to a named branch to preserve work. A detached HEAD is not preservation; garbage collection eats it.

## Remove

Inspect the directory, not the refs. A merged branch says nothing about edits left uncommitted after the commit.

Run `git status` inside the worktree. A dirty or untracked worktree is not disposable. Show the file list and the three ways out: commit to a named branch, move the files out, or delete them as unrecoverable. The coordinator or user picks. Once clean, remove with `git worktree remove`.
