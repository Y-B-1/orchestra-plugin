# Interview, glossary, decision records, questionnaire

## Round format
Number the questions. Each one:
- Title, then the body with options and trade-offs.
- Recommended answer with one reason, worded so "yes" accepts it.
Never put two dependent questions in one round. A round the owner answers moves the frontier outward: recompute it, then ask the next.

## Close the frontier
Before you call the frontier empty, score each area Clear, Partial or Missing: scope and exclusions, domain and data, user flow, limits (speed, size, cost), integrations and their failures, edge cases, rejected alternatives, terms, how anyone knows it is done. Each Partial or Missing area that would change behavior becomes a question. Skip method and task breakdown questions; planning owns them. Turn a vague word ("fast", "robust") into a measure or ask for one.

## Recurring workflows
When the owner wants a repeated job specified (a loop), grill for: the trigger (an event beats a schedule), the checkpoints where a human decides, and the brief each checkpoint shows. Push each checkpoint as late as it goes, so the owner is asked once with everything ready. Add no checkpoint, schedule or AI step the answers do not require. The spec is done when an implementer needs to ask nothing.

## Glossary
- Challenge each term against the glossary. When one conflicts, name both meanings and ask which applies.
- Replace a vague or overloaded word with one canonical term and list the rejected words as avoided names.
- Test a relationship with a concrete edge case. Check each claim about how the system works against the code and return a contradiction as a question.
- Write a resolved term in at once, never in a batch. One or two sentences, what it is, no implementation detail, only terms specific to this project. Create the file on the first term. Where a `GLOSSARY-MAP.md` exists, write to the glossary of the context the term belongs to.
- Write to the glossary only when the brief owns that file; otherwise list proposed entries in the artifact.

## Decision record
Write one only when all three hold: hard to reverse, surprising without context, a real trade-off between genuine alternatives. If one is missing, write none. A record holds the context, the choice, the rejected options and the consequences, in a few lines, under `docs/adr/NNNN-slug.md`.

## Questionnaire
Use it when the owner cannot answer alone because someone else holds the facts. Interview the send, never the subject: ask who receives it and what the owner must get back, in one exchange. Then write one Markdown file: purpose, from and to, context in one paragraph, how to answer (partial answers and "I do not know" are useful), questions grouped by theme and ordered by importance, each one idea with an answer stub and a why line only where it could be misread, and a closing "Anything else?". Done when every item the owner named is covered.
