# Visual lens

Use when the diff changes what a user sees. Judge from inspected screenshots or a live view, not from the code.

- Evidence: one inspected screenshot per required theme, viewport and state. State each one you did not see. Missing evidence for a required state is a finding.
- States: empty, loading, error, long text, many items, and permission-denied where it applies.
- Defects: clipped or overflowing text, misalignment, uneven spacing, low contrast, a missing focus ring, broken or janky motion, layout shift.
- Responsive: the required widths, including the narrowest.
- Density and style are judged in place beside the host page. The host's design vocabulary (tokens, components) is reused, not reinvented. Raw colors where tokens exist are a finding.
- Input: checks drive real events (click, key, type), not direct state changes.
- Accessibility basics from the main skill apply too: keyboard, accessible names, visible focus, color not the only signal.
- Judge a screenshot the way a user would see it at normal zoom. Zoomed detail alone does not prove the whole page is right.
