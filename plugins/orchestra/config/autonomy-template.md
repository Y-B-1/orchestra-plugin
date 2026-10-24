# Autonomy ledger

> Replace every placeholder, then run `orchestra.py autonomy arm` again. Change nothing in this file after `arm`: a change stops the loop.

goal: <one line goal>
deadline: <ISO 8601 time with a UTC offset, in the future>

- Repairs: up to 1 per chain

## Completion checks

> One check per line as `NAME: argv...`. Run each with `orchestra.py gate NAME -- argv...`. The run is complete when every check has a passed gate receipt on the current artifact.

<NAME: argv...>

## Approval boundaries

> Fixed. Do not remove a line. Add your own lines below them.
>
> <!-- Release: replace the Release line with `- Release: pre-authorized <remote> <target>` to pre-authorize the one release that policy.release configures. The Release line overrides Push and Engine-gated actions for that remote and target only. -->
>
> Autonomy may push a branch and open a pull request with `gh pr create`; the owner merges the pull requests onto the default branch after the run.

- Release: no release, permit or deploy.
- Merge: no merge into the default or a protected branch; a pull request whose base is a run branch may merge.
- Push: push any branch except the default, protected branches and tags; never force.
- Deletion: delete only what the run created: its run branches and worktrees, and files inside a linked worktree; never tags, the default branch or other branches.
- Credential entry: never enter credentials.
- Engine-gated actions: nothing that needs a permit.
