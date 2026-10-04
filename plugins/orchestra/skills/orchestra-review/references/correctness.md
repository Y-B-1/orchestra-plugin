Sentinel: orchestra-review/references/correctness.md
Stub: B4 skeleton; ticket S5 rewrites this file and removes this line.

# Code reviewer: correctness lens

1. Requirements: map changed behavior to the approved ask, journeys and constraints; flag omissions or unauthorized additions with a spec citation.
2. Correctness: trace data, error paths, boundary inputs, races and integration contracts. Test a concrete counterexample when safe.
3. Tests: check behavior assertions, pre-change failure, invalid inputs, integration coverage and stale evidence. A green mock-only test cannot prove the real boundary.
4. Standards: check applicable project rules and scope. Refer detailed conformance questions to the independent critic without skipping obvious violations here.
