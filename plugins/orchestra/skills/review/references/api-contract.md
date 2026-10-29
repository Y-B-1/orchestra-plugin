# API contract lens

Use when the diff changes a public function, endpoint, event, CLI, file format or message.

- Existing callers keep working, or every caller changes in this diff. Search for callers, including other repos' clients and docs you can see.
- Removed or renamed fields, changed types, units, nullability, defaults and ordering.
- Changed status codes, error shapes, error text callers match on.
- New required input without a default.
- Changed side effects, idempotency, pagination or rate behavior.
- A wire format read by another language or version: both sides handle both shapes during rollout.
- A breaking change needs a version, a deprecation path or an explicit owner decision in the ask.
- Docs, examples, generated clients and schema files match the new contract.
- A test pins the contract through the public interface, with an old-shape request still handled where compatibility is promised.
