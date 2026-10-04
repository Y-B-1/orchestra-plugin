Source: derived from obra/superpowers@8ca22dba9a94 skills/writing-plans/SKILL.md, skills/executing-plans/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/to-tickets/SKILL.md, skills/engineering/wayfinder/SKILL.md, skills/engineering/prototype/SKILL.md (MIT); garrytan/gstack@4015c2870b06 spec/SKILL.md (MIT); github/spec-kit@ae5ade7234be templates/plan-template.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-design/references/plan.md

# Designer-planner: plan mode

Output: one plan of tickets. Plan only. Edit no code and decide no product question.

## Start gate

Begin from the approved spec, the research, the repository facts and the binding project rules. The brief states which spec the user approved. If it does not, or the spec has an open decision that a ticket depends on, stop and mark that dependent work blocked.

Run a rules gate twice: before you slice, and again on the finished plan. Compare the plan with each binding project rule.

## Map, then slice

1. Map the files and resources the work touches and what each is responsible for. This locks the split. Group what changes together and separate what has one purpose.
2. Cut vertical slices. Each slice is a narrow but complete path through every layer it needs, verifiable alone and small enough for one fresh context. The first ticket is the thinnest end-to-end slice. Do any prefactoring before the slices that need it.
3. A wide mechanical change, such as a rename across many call sites, is the exception. Sequence it as expand, migrate in batches by blast radius, then contract. Each batch is a ticket blocked by the expand, and the contract is blocked by every batch.
4. Give every slice its class:
   - Spike: throwaway code that answers one question and reports what it proved, so a doubt becomes evidence. It is never merged.
   - Bounded: changes code whose flow already exists.
   - Architectural: adds a subsystem or changes an interface others depend on. It gets a checkpoint review.

## Write each ticket

A ticket maps to one engine card. State:
- goal, class, role and mode;
- starting artifact;
- owned paths and resources, with a name for every shared one;
- dependencies, by ticket;
- acceptance criteria and the scoped commands that check them;
- the done contract: what the report must show.

Carry each binding rule that touches the ticket into the ticket text. A link does not carry a rule into an empty worker context.

Plans decide what an implementer cannot decide alone. Give a test its name and assertions, and give code its exact signature, file and any value the spec fixes. Write a body only for an algorithm the signature and tests leave open. Strike lines that decide nothing, such as "handle edge cases". A plan several times longer than its spec has written the code instead.

## Check the graph

- Two tickets that edit one resource share an owner, or one depends on the other. Never rely on edits that happen to commute.
- Model the dependency graph. Check for cycles and unknown dependencies. Explain why the order holds.
- Test readiness: from the accepted prerequisites alone, does each queued ticket become ready? Independent tickets can start at once.
- Pre-flight: for each ticket that consumes what an earlier ticket produces, write one row with both tickets, what one produces against what the other consumes, and what you found. Rule each conflict against the spec. If tickets share nothing, write one line that says so.

## Place the reviews

Name the required checkpoint reviews for architectural foundations, the final integration review, the affected gate sets and every live check. A live check is a human step: write its exact steps. Optional full-suite testing stays on the project owner's trigger.

Route failure. For each ticket, name where a blocked review returns it.

## Self-check, then return

- Every spec requirement and every acceptance criterion maps to a ticket. List the gaps.
- Names and signatures agree across tickets.
- No ticket carries more than one fresh context of work.
- Every ticket has an owner, an acceptance command and a done contract.

Return the plan, the graph, the pre-flight rows and the gaps. State that a substantial plan needs an independent critic before any build starts.

Example: B1 owns an API adapter, B2 the settings view, B3 the documentation. B1 and B2 depend on the approved contract, and B3 starts at once. B1's checkpoint review does not wait for B2. If a shared fixture needs edits, one ticket owns it, or a dependency orders the edits.
