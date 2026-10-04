Source: derived from obra/superpowers@8ca22dba9a94 skills/writing-plans/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/prototype/SKILL.md skills/engineering/prototype/LOGIC.md skills/engineering/prototype/UI.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-critique/references/feasibility.md

# Critic: feasibility mode

Test whether the plan can be executed as written, on the real APIs and the real repository.

## Checks

- Executable step: each step lets the builder write exactly one reasonable thing. A line that decides nothing, such as "handle edge cases", is a gap. A step that spells out what its signature and tests already fix is a transcript.
- Coverage: every spec requirement maps to a task, and every input class or failure mode the spec implies has a task whose tests exercise it.
- Consistency: names, types and signatures used in later tasks match what earlier tasks define.
- Proportion. A plan several times longer than its spec has written the code instead.
- Premises: check each premise against code or primary documentation. Label it OBSERVED, REASONED (inferred) or UNKNOWN. OBSERVED means you read the file or ran the command in this assignment and saw the result. Look for an API that does not exist in the pinned version, an unsafe write, two tasks that write one path, a lease or reservation collision, and a gate that cannot fail.

## Spikes

When a premise is UNKNOWN and matters, propose a spike instead of guessing. You propose and never run it. Spike: throwaway code that answers one question and reports what it proved, so a doubt becomes evidence. State:

1. The one question, in a sentence.
2. The smallest throwaway artifact: a pure logic module for a state or data question, or a few structurally different variants on the real page for a look-and-feel question.
3. What result settles it, and what result sends the plan back.
4. Where it lives: marked as a prototype, outside production paths, with no tests and no persistence.

Recommend each spike as a Spike-class ticket.

## Routing

A settled decision that cannot work routes back to design with the evidence. A step defect routes to planning. Judge feasibility on evidence; say what you did not check.
