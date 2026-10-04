# Autonomy ledger

> Replace every placeholder, then run `orchestra.py autonomy arm` again. Change nothing in this file after `arm`: a change stops the loop.

goal: <one line goal>
max_passes: <integer, 1 to 20>
max_stalls: <integer, 1 to 2>
deadline: <ISO 8601 time with a UTC offset, in the future>

## Completion checks

> One check per line as `NAME: argv...`. Run each with `orchestra.py gate NAME -- argv...`. The run is complete when every check has a passed gate receipt on the current artifact.

<NAME: argv...>

## Approval boundaries

> Fixed. Do not remove a line. Add your own lines below them.

- Release: no release, permit or deploy.
- Merge: no pull request merge, and no local merge on the default branch.
- Push: no push to any branch.
- Deletion: no deletion of files, branches or tags.
- Credential entry: never enter credentials.
- Engine-gated actions: nothing that needs a permit.
