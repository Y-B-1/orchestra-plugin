Source: derived from garrytan/gstack@4015c2870b06 qa-only/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/prototype/UI.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-critique/references/surface.md

# Critic: surface mode (shipped-surface audit)

Audit a surface that has already shipped. Find and report; never fix. Write no tests.

## Method

1. Walk each named live surface through the user's real path, from the entry point the user actually uses. Take the common journey first, then failure and empty states.
   If you have no browser tool, say so, walk what Bash and WebFetch can reach, and list each surface you could not observe as UNKNOWN with the capture the coordinator must supply.
2. Judge each surface in place, inside the host page with its real data and density. A surface seen alone always looks fine.
3. Compare the depth built with the approved ask, and with named reference products that offer the same feature. Cite each reference concretely. Never substitute unnamed best practice.
4. Record blockers, dead ends and missing affordances. Give each finding steps to reproduce it and the evidence you collected: a screenshot, a recorded observation or a command output.

## Evidence

Tests alone do not prove appearance. Visual acceptance needs a screenshot you inspected, or a live observation through the user's path. State plainly which surfaces you could not observe and why; artifact review alone cannot prove shipped behavior.

## Findings

Each finding names: the surface, the gap, the concrete reference, the observable consequence and the smallest useful change. Rank by what the user meets first.

A chosen depth can be minimal. Report a gap only against the approved ask or a concrete reference. You supply judgment and evidence, not a mandate to add features or widen scope.
