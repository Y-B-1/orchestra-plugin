Sentinel: orchestra-operate/references/cleanup.md
Stub: B4 skeleton; ticket S7 rewrites this file and removes this line.

# Operator: cleanup mode (preservation and hygiene)

Inspect the assigned worktree, dirty/untracked bytes, named branches, live processes and transcript freshness. Merged references do not prove the directory is disposable. Propose cleanup only for owned artifacts; preserve unfinished work on a named branch before removal. Never stash shared work, rewrite live history or remove another worker's state. Check temporary files, generated drift, current project memory and final report gaps. Tracked memory changes belong before final gates; later edits invalidate evidence.

Return a cleanup proposal and preservation evidence. Removal needs coordinator assignment and applicable permission; this role does not release or own run state.
