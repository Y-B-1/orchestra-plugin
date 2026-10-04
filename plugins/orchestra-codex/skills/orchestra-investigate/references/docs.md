Source: derived from mattpocock/skills@d81f3a183412 skills/engineering/research/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-investigate/references/docs.md

# Investigator: docs mode

Answer an unknown about an external API, library or service from primary sources. Primary means official documentation, changelogs, specifications, first-party APIs and the dependency's own source at the version the project uses. A blog post or summary is a lead to follow back to the source that owns the claim.

For each claim in the report, give:
- the source URL, or the path inside the dependency;
- the access date;
- the version the source describes, and the version the project pins;
- the behavior the source supports, in your own words;
- the limits the source leaves open.

Explain how the claim applies to the brief's question. Do not paste manuals.

Rules:
- Check the project's lockfile or manifest for the version before reading any page. A page for another version is a lead.
- Do not state a post-cutoff API from memory. If no source is reachable, the claim is UNKNOWN, and the report names the source to read.
- Resolve conflicts between sources by version and date, and report the conflict.
- Do the reading yourself; do not hand it to another agent.

The coordinator caches the report as RESEARCH.md and expires it with the sprint. Say in the report which version or date change makes it stale.
