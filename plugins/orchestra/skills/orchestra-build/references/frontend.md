Source: derived from mattpocock/skills@d81f3a183412 skills/engineering/prototype/UI.md (MIT); see THIRD-PARTY-NOTICES.

Sentinel: orchestra-build/references/frontend.md

# Builder: frontend mode

Use this mode for user-visible surfaces: pages, components, styling, layout and interaction.

## Inputs

The brief names the host design vocabulary: component library, tokens, spacing and copy rules. Use those and add no new styling system. It also names the required themes, viewports and states. When any of these is missing, report a blocker; do not invent a design.

## Build

Test first still applies to behavior: state changes, validation, event handling and data shown. Write the behavior test, watch it fail, then build the view. Screenshots check layout and appearance.

Reuse existing components. Match the surrounding page in density, hierarchy and naming. Keep each state (empty, loading, error, long text) in the same component, not in a copy.

## Evidence

Evidence is a screenshot you opened and looked at, not a command that exited 0.

1. Capture every required theme, viewport and state from the brief, for example light and dark, narrow and wide, empty and full.
2. Open each image and inspect it. Name what you checked: clipped text, overflow, contrast, focus ring, alignment.
3. Run the scoped interaction checks: click, type, tab through, submit, and the failure path. Use real input events, not direct calls into the component.
4. Save the images under the log directory the brief names, never in the repository. List each path in the report with the state it shows.

A required state you could not capture is an unavailable check. Report it as unavailable; do not report the surface as verified.

## Variants

Build variants only when the brief asks for them. Then:

- Put all variants on the existing route behind a `?variant=` switch so each sits among real data and neighbors.
- Make variants differ in structure: layout, hierarchy and main action, not only color or copy. Three to five variants is the range.
- Keep variants read-only. Point any mutation at a stub.
- When a variant is chosen, fold it into the real code and rewrite it to production standard. Remove the other variants and the switcher before you commit.
