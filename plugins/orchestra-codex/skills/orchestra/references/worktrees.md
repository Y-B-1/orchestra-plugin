Source: derived from obra/superpowers@8ca22dba9a94 skills/using-git-worktrees/SKILL.md skills/finishing-a-development-branch/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/worktrees.md

# Worktrees

A worktree buys isolation and nothing else. Give one to each concurrent editor; a lone editor and a read-only worker use the main tree.

## Create

1. Detect existing isolation first: compare the git dir with the common dir. Inside a linked worktree, reuse it. In a submodule, stop and ask.
2. Prefer the host's native isolation tool; otherwise run `git worktree add` on a named branch.
3. Confirm the worktree directory is ignored by git.
4. Set up the project and run the scoped baseline checks before any edit.

One worktree serves one unit of work. The dispatcher who created it removes it in the same wave.

## Share nothing

All worktrees share one ref store. Never run `git stash` in a repository that uses them; it is repo-wide. Commit to a named branch to preserve work. A detached HEAD is not preservation.

## Remove

Inspect the directory, not the refs. A merged branch says nothing about edits left uncommitted after the commit. Run `git status` inside the worktree. Refuse to remove a dirty one: show the uncommitted paths and what is at stake, commit them to the named branch, then remove with `git worktree remove`.
