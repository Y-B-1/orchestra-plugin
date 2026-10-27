# Live gh check (L2)

`scripts/live-gh-wizard.sh` runs ledger row L2 against real `gh` on a throwaway private repository. Unit tests use a fake `gh`; only this run shows that GitHub behaves as the merge guard assumes.

## What it proves

- A merge is refused when the pull request head moved after the owner typed `approved`.
- A child pull request is retargeted to the default branch after its parent merges.
- When the parent branch is checked out in a worktree, GitHub does not retarget (ledger row G9). The guard then denies the child merge and names `gh pr edit N --base main`.

The wizard drives the hook entry point (`orchestra_hook.py`) with `UserPromptSubmit` and `PreToolUse` payloads. It does not start a Claude session.

## Who runs it

A human, once per release candidate. It needs a signed-in `gh` and creates a repository, so no agent runs it.

## Command

```
scripts/live-gh-wizard.sh OWNER/NAME
```

`OWNER/NAME` must not exist yet and must not be this repository's own remote. The wizard asks `y` at your terminal before every step that changes GitHub (create, push, pull request, merge). Anything else stops it with exit 1.

The run state lives in a scratch directory, never in your own state folder. The wizard marks the recorded pull requests as reviewed by editing the scratch state, because it tests the merge guard and not the review gate. The approved merge uses `--merge` (the only method the guard accepts), not `--squash`.

## Output

One line per check; the exit code is 0 only when all three pass.

| Line | Meaning |
| --- | --- |
| `PASS stale-head-refused` | After a push to the parent branch, the guard denied the merge with "head moved". |
| `PASS child-retargeted` | After the approved parent merge, GitHub moved the child's base to `main`. |
| `PASS worktree-child-denied` | With the parent in a worktree, the child kept its old base and the guard denied its merge with the `gh pr edit` text. |

`FAIL name: detail` says what was seen instead. If GitHub retargeted the child although the parent was in a worktree, row G9 is wrong and needs a ledger update.

## Cost and cleanup

It costs one private repository, four pull requests and a few API calls. No tokens. At the end the wizard prints, and does not run, the delete command:

```
gh repo delete OWNER/NAME --yes
```

It also names the scratch directory; remove it yourself.
