Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/task-reviewer-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/triage/OUT-OF-SCOPE.md (MIT); garrytan/gstack@4015c2870b06 review/SKILL.md (MIT); github/spec-kit@ae5ade7234be templates/commands/analyze.md (MIT); ideas: pstack (idea level); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-critique/references/scope.md

# Critic: scope mode

Compare the artifact, a plan or a diff, with the approved ask. Every change must trace to the request.

## Checks

Report these separately and never net one against the other:

- Missing: a requirement skipped, claimed without being built, or built halfway.
- Extra: a change nobody asked for. This covers unrelated files, an unrequested feature, a refactor beside the point and incidental edits that widen the blast radius.
- Misunderstood: the right feature built the wrong way, or the wrong problem solved.

Start from the stated intent: the ask, the spec's exclusions, the commit messages or card text. Then compare it with the changed paths, then with the changes themselves. Check each exclusion the spec states.

## Coverage

Map requirements to tasks. A requirement with no task, and a task with no requirement, are both findings. A success criterion that needs buildable work, such as performance or security, and appears in no task is a finding. A plan that mandates an extra is still a finding when the ask does not.

## Safety facts

Name the one or two facts the change's safety rests on, for example that no other caller depends on the old behavior. Listing callers is not proof. Require a test, script or probe that shows each fact, or report it as `unproven`. Never invent a caller or an API.

Check what a symbol search misses: wire and persisted formats that other code reads, feature flags, library source at the pinned version, and run order at teardown. List each risk you checked and ruled out, with its reason, beside the confirmed ones.

## Out of scope

Check each exclusion before you call something creep. When you find rejected scope, record it as one entry per concept: the decision, a durable reason (project focus, a technical constraint, a settled choice), and the requests it covers. A deferral for lack of time is not a rejection. Put the entry in your report for the coordinator to file.

## Limits

When a requirement cannot be judged from the diff alone, list it as unverifiable and name what to check. Do not widen the search to cover it.
