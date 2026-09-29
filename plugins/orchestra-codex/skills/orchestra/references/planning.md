# Designer-planner: planning phase

Begin with the approved spec, research, repository facts and applicable rules. Design approval is a prerequisite; planning must not make hidden product decisions.

Produce testable tickets with goal, starting artifact, owned paths/resources, dependencies, role/mode, acceptance criteria, scoped commands and done contract. Start with a thin end-to-end slice. Separate independent ownership; name unavoidable shared resources and serialize them. Carry binding rule requirements into briefs. Define required checkpoint reviews for consequential foundations, final integration review, affected gate sets and live checks. Keep optional full-suite testing on the project's owner trigger.

Model the dependency graph, check cycles and unknown dependencies, and test whether each queued ticket becomes ready from accepted prerequisites. Include realistic failure and repair routing. Submit substantial plans to an independent red team before implementation. Repair findings explicitly; unresolved spec contradictions go to design.

Example: B1 owns an API adapter, B2 owns the settings view, B3 owns documentation. B1/B2 depend on the approved contract; B3 can run immediately. B1's checkpoint review need not wait for B2. If a shared fixture needs edits, give one owner or add a dependency rather than hoping edits commute.
