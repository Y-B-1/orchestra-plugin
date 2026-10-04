Source: derived from garrytan/gstack@4015c2870b06 cso/sections/audit-phases.md (MIT); ideas: Claude Code security-review (idea level); see THIRD-PARTY-NOTICES.

Sentinel: orchestra-build/references/sensitive.md

# Builder: sensitive mode

Use this mode when the change touches authorization, authentication, secrets, personal or payment data, guards, hooks or engine state.

## Before editing

Read the binding authorization, data and engine rules the brief carries. Read the code that enforces them. Trace every permission boundary your change touches: who calls, with what identity, and what the check trusts. A caller-supplied identifier is not proof of identity. Claim no isolation that a prompt or a naming convention cannot give.

Classify the data the change reads, writes, logs or sends: credentials, personal data, payment data, internal metadata or public data. Follow it through storage, logs, errors and any outbound call.

## Build

Test first, and test the failure direction: the denied caller is denied, the malformed input is rejected, the stale evidence is refused. A test that proves only the allowed path leaves the boundary unchecked.

Fail closed. When a check cannot run or its input is missing, deny.

## Self-check

Before reporting, read your diff once for each class:

- Injection: shell, SQL, path, template or prompt text built from input.
- Authentication and session: identity taken from the caller, weak or missing checks, lease or token exposure.
- Authorization: a path that reaches the action without the check, or a check on the wrong subject.
- Secrets and data exposure: values in code, logs, errors, fixtures or reports.
- Unsafe input handling: path traversal, unchecked deserialization, unbounded size.
- Weak cryptography or randomness where a secret depends on it.
- Dependencies: a new package, its source and its install-time scripts.

Name each class you checked and what you found. No finding is a valid result.

## Secrets

Never write a credential, key or private data into the repository, a log, a fixture or a report; use a placeholder. When you meet a real secret already exposed, do not repeat its value. Report that it needs revocation and rotation. Rewriting history does not replace rotation and is not part of this card.
