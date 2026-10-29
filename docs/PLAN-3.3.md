# Orchestra 3.3 plan: capability parity with mattpocock/skills and pstack, or better

Owner standard (2026-10-29): every engineering capability in mattpocock/skills (38 skills) and pstack (67 skills) is available in Orchestra, as good or better, and no 2.15.3 capability is lost. Capabilities may be grouped into fewer skills, built into agent profiles, or put in the main skill. Each one loads by a fixed rule, so a routine unit still loads nothing.

## Coverage audit of 3.2.0 (105 source skills)

| Class | Count | Meaning |
|---|---|---|
| Covered | 25 | Orchestra already holds the behavior |
| Partial | 36 | Core idea present, a named capability missing |
| Missing | 20 | No equivalent in Orchestra |
| Out of scope | 24 | Prose style, video, personal recaps, pack setup and help, exercise scaffolding |

Regressions from 2.15.3 that 3.2.0 did not restore: wayfinder, triage, handoff, feasibility spikes, the "close the frontier" interview, the specialist review lenses (red team, data migration, API contract, visual, performance, testing), the sensitive build mode, the retro, the benchmark-vetting rule and the slop tags. The narrower guard is the owner's decision, not a regression.

## Where each capability lives in 3.3

Each row names the home and the rule that loads it. Sources: m = mattpocock/skills@59db609, p = pstack@47c6f80, o = Orchestra 2.15.3.

| Home | Capabilities folded in | Loads when |
|---|---|---|
| `decide` (shared) | grill-me, grilling, grill-with-docs, loop-me (m); "close the frontier" interview (o); domain glossary and ADR upkeep, to-questionnaire (m); exhaust the design space, redesign from first principles, experience first, model the domain (p) | Two asks conflict, an ask has two product shapes, a suggestion would break behavior, or the owner asks to be grilled. Interview mode with the owner present; decide-and-log mode under `/goal` |
| `plan` (role) | to-spec, to-tickets (m); architect type and signature sketch (p); dependency map, wayfinder decision map (m, o) | A planned ask, or a large feature whose shape is a real choice |
| `large-work` (shared) | wayfinder and figure-it-out hypothesis log (m, p); triage of task size and bug reports (o); handoff document (m, o); show-me-your-work decision log (p); foundational thinking, outcome-oriented execution, build the lever (p); feasibility spikes and throwaway prototypes (m, o); arena of candidate designs (p) | An ask too big for one builder in about 20 minutes, unknowns, a long or overnight run, or a context nearing its limit |
| `review` (role) lenses | codebase-design and improve-codebase-architecture deep modules (m); thermo-nuclear code quality: condition growth, abstraction quality (p); slop, deslop, no-comments cleanliness (p, o); interrogate red team (p, o); benchmark checklist and explain the number (p, o); type-system discipline and TypeScript practice (p); boundary discipline, idempotency, minimize reader load (p); blast radius run proof (p); data migration, API contract, visual specialists (o) | The scan or the diff shows the matching risk; the main skill names the lens in the brief |
| `build` (role) modes | sensitive mode for auth, secrets and money (o); cleanup mode with deslop and comment rules (p, o); lever mode, a codemod or script instead of hand edits (p); migrate callers then delete (p) | The brief names the mode |
| `ship` (new shared) | pr and make-pr-easy-to-review (m, p); get-pr-comments and address them (p); fix-ci from the PR's failing checks (p); fix-merge-conflicts (p); babysit a PR until green (p); setup-pre-commit (m) | Opening, updating or fixing a PR, a merge conflict, red CI, or review comments |
| `investigate` (role) | how: walkthrough and placement answer (p); why: rationale from git history and PRs (p); research with sources (m) | A how, where or why question, or docs research |
| `diagnose` (shared) | diagnosing-bugs (m); attack the premise, fix root causes (p); correct: apply one correction repo-wide (p) | Unknown bug cause, a fix that did not hold, or an owner correction |
| `verify` (new shared) | create and maintain a project verification driver (p); statechart model of a flow with states and events (p); prove it works (p) | A flow with many states (booking, payments, sync), or a repo with no way to drive the real app |
| Main skill | routing table for every row above; retro after a bug fix or an owner correction (m, o): name the missing check and add it | Always (it is the coordinator) |

Out of scope, by design: prose-writing skills, video and personal recaps, pack setup, help and mode switches, exercise scaffolding. Formal verification (TLA+ style) stays out; the `verify` statechart covers the practical part.

## Validation

1. Each folded capability gets one check line in a coverage table (`docs/COVERAGE.md`): source skill, Orchestra home, the rule text that carries it.
2. A harder benchmark, built from the owner's own rework patterns (where the first answer was wrong and the owner had to ask again), measures "right the first time": tasks F and G, plus the five existing tasks.
3. Arms: plain Claude Code, mattpocock/skills, pstack, Orchestra 3.2.0, Orchestra 3.3.0. 3.3.0 ships only if it is at least as good as the best arm on quality and passes the keep rule against 3.2.0.
