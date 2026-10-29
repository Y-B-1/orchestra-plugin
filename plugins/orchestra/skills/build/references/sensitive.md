# Sensitive mode

Use when the change touches authorization, authentication, secrets, personal or payment data, or guards.

## Before editing
- Read the authorization, data and engine rules the brief carries, and the code that enforces them.
- Trace every permission boundary you touch: who calls, with what identity, what the check trusts. A caller-supplied identifier is not proof of identity.
- Classify the data you read, write, log or send: credential, personal, payment, internal or public. Follow it through storage, logs, errors and outbound calls.

## Build
- Test the failure direction first: the denied caller is denied, the malformed input is rejected, the stale evidence is refused. A test of only the allowed path leaves the boundary unchecked.
- Fail closed in the code you write. When a check cannot run or its input is missing, deny.

## Self-check
Read your diff once per class and name each class with what you found. No finding is a valid result.
- Injection: shell, SQL, path, template or prompt text built from input.
- Authentication and session: identity taken from the caller, weak or missing checks, token or lease exposure.
- Authorization: a path to the action without the check, or a check on the wrong subject.
- Secrets and data exposure: values in code, logs, errors, fixtures or reports.
- Unsafe input: path traversal, unchecked deserialization, unbounded size.
- Weak cryptography or randomness where a secret depends on it.
- Dependencies: a new package, its source, its install-time scripts.

## Secrets
- Never write a credential, key or private data into the repository, a log, a fixture or a report. Use a placeholder.
- When you meet a real exposed secret, do not repeat its value. Report that it needs revocation. Rewriting history does not replace rotation; do not rewrite history.
