# Source skill coverage

This file lists every skill in mattpocock/skills@59db609 and pstack@47c6f80 and shows where Orchestra 3.3.0 covers each one. Here is how it was checked. Two independent audits read each source skill in full and compared it with the Orchestra text. Each source skill got one of these classes: BETTER, EQUAL, WORSE (a step is missing), UNREACHABLE (the text exists but nothing loads it in the source's situation) or OUT OF SCOPE. The gaps were fixed. A third check then read each row that had been WORSE or UNREACHABLE again, this time against the released text. A row counts as WORSE only when the missing step changes what an engineer does or produces. Orchestra loads its text in these ways. The main session reads the routing table in skills/orchestra/SKILL.md (section 3 for situations, section 4 for unit kinds). Each agent file in agents/ names the role skill it loads (build, review, plan, critique, investigate, operate). Role and situation skills (decide, diagnose, test-quality, frontend-proof, large-work, ship, verify) load only when their situation applies. A file under a skill's references/ folder is read only when a routing row, an agent file or a skill names it. All paths below are relative to plugins/orchestra/.

## Counts

| Pack | BETTER | EQUAL | WORSE | UNREACHABLE | OUT OF SCOPE | Total |
|---|---|---|---|---|---|---|
| mattpocock/skills@59db609 | 3 | 26 | 0 | 0 | 9 | 38 |
| pstack@47c6f80 | 2 | 49 | 0 | 0 | 16 | 67 |

## mattpocock/skills@59db609

| Source skill | Class | Where in Orchestra | How it loads |
|---|---|---|---|
| engineering/grill-with-docs | EQUAL | skills/decide/SKILL.md Interview mode; skills/decide/references/interview.md Glossary, Decision record | Section 3 decide row (grilled or interviewed, a term defined, an ADR) |
| productivity/grill-me | EQUAL | skills/decide/SKILL.md Interview mode | Section 3 decide row |
| productivity/grilling | EQUAL | skills/decide/SKILL.md Interview mode; skills/decide/references/interview.md Round format | Section 3 decide row |
| productivity/wait-what | OUT OF SCOPE | Re-pitching a message; communication, not engineering | |
| engineering/research | EQUAL | skills/investigate/SKILL.md Research mode; agents/investigator-research.md (returns the notes file, the main session saves it) | Section 4 investigator-research row; the agent loads orchestra:investigate |
| productivity/handoff | EQUAL | skills/large-work/references/handoff.md Write a handoff | Section 3 large-work row (the owner asks for a handoff document) |
| engineering/implement | EQUAL | skills/orchestra/SKILL.md sections 4 and 5; agents/builder.md | Coordinator skill in the main session; builder agent file |
| in-progress/claude-handoff | EQUAL | skills/large-work/references/handoff.md Write a handoff (`claude --bg --name`) | Section 3 large-work row (hand the work to a fresh background agent) |
| engineering/prototype | EQUAL | skills/large-work/references/spikes.md Spike, Pick the shape, Capture | Section 3 decide row (wants a prototype); large-work Premises and spikes |
| in-progress/loop-me | EQUAL | skills/decide/references/interview.md Recurring workflows | Section 3 decide row |
| engineering/tdd | EQUAL | agents/builder.md Tests (red first, one slice at a time, expected values from the spec, mock only system boundaries); skills/plan/SKILL.md test seams | Builder agent file, every unit; planner for seams |
| engineering/implement-spec | EQUAL | skills/orchestra/SKILL.md sections 4 and 5; skills/orchestra/references/finish.md | Coordinator skill |
| engineering/retro | EQUAL | skills/orchestra/references/finish.md Retro on request; skills/orchestra/SKILL.md Retro line | Section 3 retro row |
| engineering/wizard | EQUAL | skills/orchestra/references/finish.md Steps only a person can take | Section 3 retro and wizard row |
| productivity/to-questionnaire | EQUAL | skills/decide/references/interview.md Questionnaire | Section 3 decide row (a questionnaire for someone else) |
| in-progress/writing-beats | OUT OF SCOPE | Prose writing | |
| in-progress/chief-of-staff | EQUAL | skills/orchestra/SKILL.md section 4 and /goal; skills/large-work/references/handoff.md and run-log.md; skills/orchestra/references/finish.md | Coordinator skill; commands/goal.md; section 3 large-work row |
| engineering/improve-codebase-architecture | EQUAL | skills/investigate/SKILL.md Survey mode (hot spots, deletion test, cards, ADR check, ADR offer on rejection) | Section 3 survey row, then orchestra:decide |
| engineering/domain-modeling | EQUAL | skills/decide/references/interview.md Glossary, Decision record | Section 3 decide row |
| engineering/to-spec | EQUAL | skills/plan/SKILL.md PRD mode | Section 3 spec, PRD or tickets row; agents/planner.md loads orchestra:plan |
| engineering/to-tickets | EQUAL | skills/plan/references/tickets.md (slices, blockers, expand and contract, quiz, tracker publish) | Section 3 spec, PRD or tickets row; planner Ticket mode |
| engineering/code-review | EQUAL | skills/orchestra/SKILL.md section 5; agents/reviewer.md; skills/review/SKILL.md; skills/review/references/cleanliness.md | Section 3 review a branch or PR row; reviewer agents |
| engineering/setup-matt-pocock-skills | OUT OF SCOPE | Setup for the source pack | |
| engineering/ask-matt | OUT OF SCOPE | Router and help for the source pack | |
| productivity/writing-for-agents | OUT OF SCOPE | Writing style for agent documents | |
| misc/setup-pre-commit | BETTER | skills/ship/references/pre-commit.md | Section 3 ship row (pre-commit hooks) |
| misc/git-guardrails-claude-code | EQUAL | skills/ship/references/guardrails.md | Section 3 ship row (git guardrails) |
| misc/scaffold-exercises | OUT OF SCOPE | Course exercise scaffolding | |
| misc/migrate-to-shoehorn | EQUAL | skills/build/SKILL.md Lever mode (partial-data helpers in test files) | Section 4 builder-mechanical row |
| in-progress/setup-ts-deep-modules | EQUAL | skills/build/SKILL.md Lever mode, module-boundary bullet | Section 4 row "Enforce module boundaries"; builder loads orchestra:build when the brief names a mode |
| engineering/triage | EQUAL | skills/large-work/references/triage.md | Section 3 large-work row (triage issues or PRs) |
| engineering/codebase-design | EQUAL | skills/review/references/architecture-depth.md; skills/plan/references/sketch.md; skills/large-work/references/spikes.md Candidate designs | Section 5 architecture-depth lens; planner Sketch mode |
| engineering/wayfinder | EQUAL | skills/large-work/references/map.md | Section 3 large-work row; large-work Map before you cut |
| engineering/diagnosing-bugs | BETTER | skills/diagnose/SKILL.md | Section 3 diagnose row |
| productivity/teach | OUT OF SCOPE | Personal learning | |
| engineering/pr | BETTER | skills/ship/references/pr-body.md | Section 3 ship row |
| in-progress/writing-fragments | OUT OF SCOPE | Prose writing | |
| in-progress/writing-shape | OUT OF SCOPE | Prose writing | |

## pstack@47c6f80

| Source skill | Class | Where in Orchestra | How it loads |
|---|---|---|---|
| architect | EQUAL | skills/plan/references/sketch.md (ground, usage first, design twice, red flags, contract, scrap; a hard-to-reverse shape goes to Candidate designs) | Section 4 refactor row and new feature row; planner Sketch mode |
| arena | EQUAL | skills/large-work/references/spikes.md Candidate designs | Section 3 arena row |
| automate-me | OUT OF SCOPE | Authoring personal mode skills | |
| babysit | EQUAL | skills/ship/SKILL.md Watch a PR until green, Red CI, Review comments, Merge conflicts | Section 3 ship row |
| benchmark-checklist | EQUAL | skills/review/references/measurement.md | Section 3 measurement row; agents/builder.md |
| blast-radius | EQUAL | skills/review/references/blast-radius.md | Section 3 blast-radius row; section 5 blast-radius lens |
| bro | OUT OF SCOPE | Prose restatement | |
| correct | EQUAL | skills/diagnose/references/correct.md | Section 3 correction row (diagnose correct mode) |
| create-formal-verification-skill | OUT OF SCOPE | Formal verification | |
| create-verification-skill | EQUAL | skills/verify/references/driver.md Build | Section 3 verify row (no way to run and drive the real app) |
| deslop | EQUAL | skills/build/references/cleanup.md Slop to remove | Section 6, every diff; agents/builder-cleanup.md |
| figure-it-out | EQUAL | skills/large-work/references/run-log.md | Section 3 large-work row |
| fix-ci | BETTER | skills/ship/SKILL.md Red CI | Section 3 ship row |
| fix-merge-conflicts | EQUAL | skills/ship/SKILL.md Merge conflicts | Section 3 ship row |
| get-pr-comments | EQUAL | skills/ship/SKILL.md Review comments | Section 3 ship row |
| how | EQUAL | skills/investigate/SKILL.md How mode | Section 3 how, where or why row |
| in-your-own-words | OUT OF SCOPE | Prompt restatement | |
| interrogate | EQUAL | skills/orchestra/SKILL.md deep review row; skills/review/references/red-team.md | Section 3 deep or adversarial review row |
| ketchup | OUT OF SCOPE | Personal recap | |
| ketchup-video | OUT OF SCOPE | Video | |
| maintain-formal-verification-skill | OUT OF SCOPE | Formal verification | |
| maintain-verification-skill | EQUAL | skills/verify/references/driver.md Maintain | Section 3 verify row (a unit changes a flow the driver covers); verify Pick the part |
| make-pr-easy-to-review | EQUAL | skills/ship/SKILL.md Make it easy to review; skills/ship/references/pr-body.md | Section 3 ship row |
| no-comments | EQUAL | skills/build/references/cleanup.md Slop to remove; skills/review/references/cleanliness.md Comments | Section 6, every diff; agents/builder-cleanup.md; cleanliness lens |
| poteto-help | OUT OF SCOPE | Help for the source pack | |
| poteto-mode | OUT OF SCOPE | Mode switch for the source pack | |
| principle-attack-the-premise | EQUAL | skills/diagnose/SKILL.md Attack the premise | Section 3 diagnose row |
| principle-boundary-discipline | EQUAL | skills/review/references/boundaries.md | Section 5 boundaries lens |
| principle-build-the-lever | EQUAL | skills/build/SKILL.md Lever mode; skills/large-work/SKILL.md Run in verifiable units | Section 4 builder-mechanical and Lever mode rows |
| principle-encode-lessons-in-structure | EQUAL | skills/orchestra/SKILL.md Retro line; skills/orchestra/references/finish.md Make the next run easier | Coordinator skill |
| principle-exhaust-the-design-space | EQUAL | skills/decide/references/shapes.md | Section 3 decide row |
| principle-experience-first | EQUAL | skills/decide/references/shapes.md | Section 3 decide row |
| principle-explain-the-number | EQUAL | skills/review/references/measurement.md | Section 3 measurement row |
| principle-fix-root-causes | EQUAL | skills/diagnose/SKILL.md; skills/build/SKILL.md All builders | Section 3 diagnose row; builder when a mode is named |
| principle-foundational-thinking | EQUAL | skills/large-work/SKILL.md Freeze the interface | Section 3 large-work row |
| principle-guard-the-context-window | EQUAL | agents/builder.md time cap; skills/large-work/SKILL.md Hand off | Builder agent file; section 3 large-work row |
| principle-laziness-protocol | EQUAL | skills/build/SKILL.md All builders; agents/builder.md smallest change | Builder agent file |
| principle-make-operations-idempotent | EQUAL | skills/review/references/boundaries.md Idempotency | Section 5 boundaries lens |
| principle-migrate-callers-then-delete-legacy-apis | EQUAL | skills/build/SKILL.md Migrate mode | Section 4 Migrate mode row |
| principle-minimize-reader-load | EQUAL | skills/review/references/architecture-depth.md Reader load | Section 5 architecture-depth lens |
| principle-model-the-domain | EQUAL | agents/builder.md data shape rule; skills/decide/references/shapes.md | Builder agent file; section 3 decide row |
| principle-never-block-on-the-human | EQUAL | skills/decide/SKILL.md Decide-and-log mode; commands/goal.md | Coordinator /goal section; section 3 decide row |
| principle-outcome-oriented-execution | EQUAL | skills/large-work/SKILL.md Run in verifiable units | Section 3 large-work row |
| principle-prove-it-works | EQUAL | skills/verify/SKILL.md Prove it works; skills/orchestra/references/finish.md Evidence; skills/test-quality/SKILL.md | Section 3 verify row; coordinator section 7 |
| principle-redesign-from-first-principles | EQUAL | skills/decide/references/shapes.md | Section 3 decide row |
| principle-separate-before-serializing-shared-state | EQUAL | skills/orchestra/SKILL.md section 4 worktree rule; skills/large-work/SKILL.md Freeze the interface | Coordinator skill |
| principle-sequence-verifiable-units | EQUAL | skills/large-work/SKILL.md Run in verifiable units; skills/ship/SKILL.md Make it easy to review | Section 3 large-work and ship rows |
| principle-subtract-before-you-add | EQUAL | skills/large-work/SKILL.md Freeze the interface; skills/build/references/cleanup.md | Section 3 large-work row; section 6 |
| principle-test-behavior-not-implementation | BETTER | skills/test-quality/SKILL.md A test worth keeping | Section 3 test-quality row |
| principle-type-system-discipline | EQUAL | skills/review/references/types.md | agents/builder.md typed code rule; section 5 types lens |
| recall | OUT OF SCOPE | Personal recap; the in-run resume part is EQUAL in skills/large-work/references/handoff.md Resume | |
| reflect | EQUAL | skills/orchestra/references/finish.md Retro on request | Section 3 retro row |
| setup-pstack | OUT OF SCOPE | Setup for the source pack | |
| sharpen | OUT OF SCOPE | Prompt rewriting | |
| show-me-your-work | EQUAL | skills/large-work/references/run-log.md Decision log | Section 3 large-work row |
| statechart | EQUAL | skills/verify/references/statechart.md | Section 3 verify row (a flow with many states) |
| swarm | EQUAL | skills/orchestra/SKILL.md section 4 Workflow; skills/large-work/references/run-log.md | Coordinator skill |
| tdd | EQUAL | agents/builder.md Tests; skills/build/SKILL.md All builders; skills/diagnose/SKILL.md Prove the fix | Builder agent file |
| teach | OUT OF SCOPE | Explanation style; the engineering part is investigate How and Why modes | |
| technical-writing | OUT OF SCOPE | Prose style | |
| thermo-nuclear-code-quality-review | EQUAL | skills/review/references/cleanliness.md Growth, Code judo (blocking in a deep or thermo review) | Section 3 deep or thermo review row, cleanliness lens |
| thermo-nuclear-review | EQUAL | skills/review/references/red-team.md | Section 3 deep review row, red-team lens |
| thermos | EQUAL | skills/orchestra/SKILL.md deep review row | Section 3 deep review row |
| typescript-best-practices | EQUAL | skills/review/references/types.md | agents/builder.md (read before adding a type, a parse or a cast); section 5 types lens |
| unslop | OUT OF SCOPE | Prose style | |
| what-did-i-get-done | OUT OF SCOPE | Personal recap | |
| why | EQUAL | skills/investigate/SKILL.md Why mode | Section 3 how, where or why row |

## Rows still WORSE or UNREACHABLE

None.

## Smaller notes, fixed

The third check also found five smaller loading gaps. None changed a class, and all five are fixed in 3.3.0: the main skill names the types lens for any new type, interface or optional field; the spec row names PRD mode; the cleanup builder may load `orchestra:investigate` why mode when cleanup.md names it; PRD mode applies the `ready-for-agent` label; and the verify row covers a request to audit or update the driver.
