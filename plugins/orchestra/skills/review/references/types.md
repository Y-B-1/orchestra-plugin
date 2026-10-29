# Types lens

Use for typed code. A type that lets an illegal state exist is a finding when a caller can reach it.

## Rules
- Make illegal states unrepresentable. Variants carry a literal `kind`; no bag of optional fields where some combinations are invalid.
- Brand semantic primitives. If two arguments share a type but mean different things (user id, order id), they get distinct types, made once at a verifying parse or guard.
- External data is `unknown` until parsed: JSON, RPC payloads, env vars, CLI args, config, database rows. A parse function sits at each boundary and returns the named domain type. Inside, trust the type.
- Derive a type from the authority that owns the shape (schema, spec, migration, token file). A hand-written parallel type will drift.
- Build the shape so the bad value cannot be made (non-empty tuple, start plus duration). Keep the loose type while every operation stays total; tighten only where a `!`, a cast or a "never happens" throw appears.
- Every variant switch ends in an exhaustiveness check, so a new variant breaks the build.

## TypeScript
- `unknown`, never `any`, for outside data.
- No `as` to get past the checker. Cast only after validation. Prefer `satisfies` to keep literals.
- Narrowing order: discriminant switch, `in`, `typeof` or `instanceof`, a type guard, then `as`.
- A type guard must verify what its name claims. A guard that returns true unchecked is worse than a cast.
- Use the repo's runtime schema library and infer the type from it before hand-writing a guard.
- Prefer `Pick`, `Omit`, `Parameters`, `ReturnType`, `Awaited` over a new interface.
- Pass an object for three or more parameters, except on hot paths.
- No `console.log` in shipped code; use the project logger with an id.

## Ask of the diff
- Which new `any`, `as`, `!` or `@ts-ignore` hides a real invariant? Name the invariant.
- Which new optional field is really two variants?
- Which new string or number needs a brand?
