# Pulse project rules

- TypeScript strict mode stays on. No `any` without a reason.
- Tests live next to the code they cover (`foo.ts` and `foo.test.ts`).
- Commit with explicit paths; never stage the whole tree.
- Keep colors, fonts and spacing in the CSS variables in `src/styles/theme.css`; do not hard-code them in components or in `global.css`.
- Before committing, run `npm run typecheck`, `npm run lint`, `npm test` and `npm run build`.
