# Build ledger

Status: CHECKED. Ten worker contracts plus main, native matrices and GitHub distribution are approved. No production target or classifier service is configured. The application reference stayed read-only.

| Ticket | State | Evidence |
| --- | --- | --- |
| T1 | BUILT | Engine, card/evidence/lease tests and completion checks |
| T2 | BUILT | Shared parser and native hooks; covered malformed and release cases |
| T3 | BUILT | Progressive skill, all roles/modes, canonical native matrices |
| T4 | BUILT | Both native installs/removals exit 0; safe profiles; reproducible archives |
| T5 | CHECKED | 84 tests pass; code review and spec audit CLEAN; local bare-target release matches full HEAD; skill forward-test complete |

Implementation candidate a82d3e01859193ea2b85fc54c7cff6d7accdde4e received independent Sol code-review and spec-audit CLEAN verdicts. The root ran all 84 tests at that candidate, exit 0. Earlier findings received regression-backed repairs for review integrity, repair scheduling, leases, state paths, command parsing and exact Git source/context binding. Known Git releases now use a finite direct four-argument recipe.

Final release metadata needs a documentation-delta check and renewed gates. The GitHub release records the exact published commit and archive checksums. Native hook trust remains a user activation check, not a waived gate.

Native model evidence: older Codex CLI 0.158.0 rejected Sol, while desktop-bundled 0.159.0 ran Sol medium and a named Luna-high discovery worker successfully. Claude OAuth expired. Native metadata installation succeeds for both clients. Native hook trust was not written or bypassed. User hook review/trust remains a separate activation check. See VALIDATION.md.

## 1.0.1 update — 2026-09-30

The update removes Astra from Codex routing, adds reserved inline assignments beside disjoint workers, and fixes native hook discovery. Codex 0.159.0 selects the generated compatibility package; the canonical portable manifest and Claude package stay separate. All 44 native package bytes and 27 profiles match generation. The suite passes 89 tests; native isolated hook listing returns five untrusted definitions exactly once. Final artifact review and publication receipts follow these checks. No hook trust is written.

## 2.0.0 build — 2026-10-04

Tracked here, not in the v1 engine (PLAN-v2 0.1). Integration is serial: merge, checkpoint review on the merged commit, accept (PLAN-v2 0.3). Worktrees live under the session scratchpad (`$SCRATCH/wt/<ticket>`).

| Card | Owner | Worktree | Merged commit | Review verdict | Acceptance |
| --- | --- | --- | --- | --- | --- |
| I1 | investigator | none | 512bfac (RESEARCH-v2) | coordinator check | ACCEPTED |
| I2 | investigator | none | 512bfac (RESEARCH-v2 I2) | coordinator re-check of SHAs and licenses | ACCEPTED |
| P0 r1 | critic feasibility + scope | none | e9140d0 (round 5 repair) | ISSUES FF1-FF3, SF1-SF10, routed to designer-planner | REPAIRED |
| P0 r2 | critic feasibility + scope | none | 3e0889d (round 6 repair) | ISSUES F1-F5, N1-N4 (planning only); all FF/SF RESOLVED | REPAIRED; P0 accepted for B1 scope |
| MX | investigator (matrix) | main checkout (one-time exception, PLAN round 6) | 6003c11 | coordinator check: one path, no personal paths | REPAIRING (MXR r1 ISSUES, 8 content findings; routed to MX-r1); ACCEPTED at MX r3 |
| B1 | builder | $SCRATCH/wt/B1 | 2c515f5 (425758e, 31ef9b2, 25bf9da coordinator fix: host-written tsconfig.json excluded and gitignored, scope extension) | R1 CLEAN; SPEC 10.2 fallback used (validator rejects `typeof $.x`; load-time validation instead) | ACCEPTED; live steps pending (heartbeat advance, interactive /exit, one SessionStart context); release build rerun owed to G1 |
| R1 F1 | design gap | none | n/a | session.end on /clear or resume stops the tick; new id never gets a marker | ROUTED to designer-planner before B5; R1 F2-F4 folded into B5 |
| MX r1/r2 | investigator (matrix) | $SCRATCH/wt/MX-r1, wt/MX-r2 | c48a537 (8dab619), b4d8fc8 (3635fc1) | MXR r2 ISSUES N1-N6 + nits, all addressed in 3635fc1; ruling N7 (cso narrowing counts as "adds to", deviation 10) | REPAIRING; MXR r3 running on b4d8fc8 |
| MX r3 | investigator (matrix) | $SCRATCH/wt/MX-r3 | ad302b8 (55b6467) | MXR r3 PASS (elems/lic/dest exit 0; one non-blocking wording note, deviation 7) | ACCEPTED: MX complete; unblocks S0 |
| D1 | coordinator design | $SCRATCH/wt/D1 | 1570009 (98062d9, 72a3cae, 583ebd0, fb67efc) | red team r1 BLOCKED, r2 BLOCKED, r3 CLEAN | ACCEPTED: SPEC 10.3 marker lifecycle; PLAN B5 acceptance |
| B2 | builder | $SCRATCH/wt/B2 | ff54311 (836db53) | R2 BLOCKED: F1 heredoc bodies piped to a shell bypass always-deny (coordinator probe confirmed 5 shapes); F2 corpus misses 9 inline test_hooks commands; F5 bare-common-dir integration case missing; F3/F4/F6 design | REPAIRING: D3 design, then B2-r1 |
| B4 | builder | $SCRATCH/wt/B4 | 318ce00 (376d973) | R4 CLEAN; F1 planning (Stub: test vs S1-S7) and F2 (code-reviewer prompt vs E7) routed to D3/S0; F3/F5 to S3/S6/S1 briefs; F4 to B7/B8 | ACCEPTED; full suite 161 OK on 318ce00; live steps pending |
| D2 | coordinator design | $SCRATCH/wt/D2 | 0ad01c0 (aabe806, 45da9c7, D2-r2 N1-N3 wording) | red team r1 ISSUES F1-F9, r2 PASS (N1-N3 low wording folded in); RESEARCH Q4 line 38 premise stale (note for INT) | ACCEPTED: O6 rebind on clear/resume/fork, dead-id recovery |
| D3 | coordinator design | $SCRATCH/wt/D3 | f291bcf (7f86f8b, 6d16873, c1c24d5) | red team r1 ISSUES F1-F10, r2 8/10 RESOLVED + N1-N4 text, fixed in c1c24d5 (grep-checked per red team) | ACCEPTED: A5 rules 1-5 (rule 5 = v1-style always-deny scan, default for the morning), runtime guard digest, A15 without --path-format, S0 Stub/Sentinel test rule |
| B2-r1 | builder | $SCRATCH/wt/B2-r1 | f009801 (0b66278) | R2b ISSUES: F1 MAJOR corpus misses 10 A2 loop commands (test_hooks 204-208) and walker skips loop lists; F2 minor 5 concatenated B2-r1 commands + refspec loop missing; F3/F4 design (eval placeholder denies; pre-existing v1 always-deny bypass via here-string, process substitution, pipe to shell); F5 plan wording (append-only vs required flip). Heredoc repairs hold (~100 probes). Ticket tests, --check, full suite 181 OK on 2b3af02 | REPAIRING: D4 (A5 rule 6), then B2-r2 |
| S0 | builder | $SCRATCH/wt/S0 | 2b3af02 (c4cec68) | R-S0 CLEAN; minor test-hardening findings 1-3 (license text not pinned, header grammar lax, header position unchecked) routed to S0-r1 | ACCEPTED; full suite 181 OK on 2b3af02 |
| D4 | coordinator design | $SCRATCH/wt/D4 | 03c4ca5 (16414e6, 6bffcdb, 3882aca) | red team r1 ISSUES F1-F11; r2 narrow re-check: F1-F4, F6-F10 resolved, F5 and N1-N5 wording, applied in 3882aca (red team: no further round needed) | ACCEPTED: A5 rule (6) here-strings as rule 1, always-deny scan of process substitution/pipes/-c args/substitutions, xargs/find -exec/doas/stdbuf/watch/flock runners; B2-r2 card in PLAN |
| B3 | builder | $SCRATCH/wt/B3 | 7219283 (3de8edc) | R3 CLEAN; minor F2 (no-op state rewrite in end_harness_session/mark_harness_rebind) and F3 (SessionEnd engine-build failure silent) carried to B8; F1 (A11 Codex `orchestra_` agent_type gets no SubagentStart context) planning, open item | ACCEPTED; modules + --check 0 on 7219283; live steps pending |
| S0-r1, S1-S7 | builder | $SCRATCH/wt/S* | f9ee002..a707b98, 8a37c8d (S1, generated profile conflicts regenerated) | test_skills + --check 0 per merge; full suite 183 OK on a707b98; SC ISSUES: 3 major (repair-rounds round-3 break, deletion test inverted, E6 reviewer half missing) + minors; O15 ruling (SPEC 8.4) | REPAIRING: SC-r1, then fresh SC |
| S8 | builder | $SCRATCH/wt/S8 | 6a952d9 (92244d5) | docs only; greps per brief; covered by final lens round | ACCEPTED (mechanical docs; final review covers) |
| B2-r2 | builder | $SCRATCH/wt/B2-r2 | b866588 (6f59b03) | modules + --check 0 after merge; 84 corpus cases appended, no flips; R2c ISSUES: 2 MAJOR (6b) bypasses (unquoted/nested substitution in -c/eval; multi-command consumer group), 1 minor ruled O16 | ACCEPTED via B2-r3 |
| B8 | builder | $SCRATCH/wt/B8 | 75c0044 (1f4ee7d) | full suite 227 OK on 3514344; R8 CLEAN; minors F1 (orchestrator mode outside contract hash), F2 (cli.md:16 stale rubric sentence), F3 (interrupt_active no-write test) carried to B9 | ACCEPTED |
| SC-r1 | builder | $SCRATCH/wt/SC-r1 | 3514344 (4f8fc08) | test_skills + --check 0 after merge; all 19 rulings mapped; checkpoint findings not in SC queued as SC-r1b; fresh SC after SC-r1b | REPAIRING: SC-r2 (SC2 ISSUES, 1 major) |
| B2-r3 | builder | $SCRATCH/wt/B2-r3 | e838fed (ae86e66) | test_skills + --check 0 after merge; 10 red corpus cases then green, 18 cases appended, no flips; group consumer counts with any shell (coordinator: accepted, conservative); R2d pending | ACCEPTED: R2d meets acceptance, no regression (326 cases, append-only); R2d major (reserved words/groups, also in v1) and 3 minors -> B2-r4 (O17) |
| SC-r1b | builder | $SCRATCH/wt/SC-r1b | 0e2fd6c (0ec2ee7) | test_skills + --check 0 after merge; 9 checkpoint findings fixed or already fixed; header_in stricter; SC2 (fresh cohesion audit) pending | REPAIRING: SC-r2 (SC2 ISSUES, 1 major) |
| B9 | builder | $SCRATCH/wt/B9 | 2bd2210 (a407a03) | test_skills + --check + engine + integration 0 after merge; full suite 241 OK in worktree; R8 F1-F3 fixed; mixed-union scope follows SPEC text (O3 reading) | ACCEPTED via B9-r2 (R9c CLEAN) |
| B2-r4 | builder | $SCRATCH/wt/B2-r4 | 38d78a8 (1fe405f) | skills + --check 0 after merge; 40 red then green, 64 corpus cases appended, one flip ($'a\'b' allows); R2d probe all benign allow; R2e CLEAN (5 minors, pre-existing shapes, ruled O20) | ACCEPTED; O20 shapes -> B2-r5 |
| SC-r2 | builder | $SCRATCH/wt/SC-r2 | 6db8eaf (6ec577f) | skills + --check 0 after merge; full suite 251 OK in worktree; rulings 1-7 applied; SC3 CLEAN (3 minors: code.md duplicate, final-review critic path, deletion-test duplicate) | ACCEPTED; minors -> SC-r3 |
| B5 | builder | $SCRATCH/wt/B5 | 48157fd (ea679df) + b33b098 fixtures resync | skills + --check 0 after merge; plugin test 39/39 incl. corpus parity with B2-r4 cases (logs/feat-parity-post-B5.log); live items to wizard; R5 ISSUES: MAJOR fail-open when a re-fired session.start throws while the old marker is fresh (probe confirmed); minors to builder; capacity and negative standing-orders cache ruled O21; parity 0 mismatches over ~28k cases | ACCEPTED via B5-r2 (R5c CLEAN) |
| B9-r1 | builder-repair | $SCRATCH/wt/B9-r1 | d68c2e9 (366dd8b) | O19 applied; 3 new tests; full suite 254 OK in worktree; engine + integration 0 after merge R9b ISSUES: cross-category stale BLOCKED leaves an older CLEAN current (spec gap, ruled O22) | ACCEPTED via B9-r2 (R9c CLEAN) |
| B2-r5 | builder | $SCRATCH/wt/B2-r5 | 4906d2e (fd1cc97) | 33 corpus cases appended (21 red then green), no flips; full suite 254 OK; probe 14 flips all target shapes; command-position $(...) gap ruled O23; R2f ISSUES: backticks drop release/boundary class (major), nested escaped backticks (minor), ruled O25 | ACCEPTED via B2-r7 (R2h) |
| B5-r1 | builder-repair | $SCRATCH/wt/B5-r1 | 2847337 (73fc92b) + 296f8f3 fixtures resync | plugin test 50/50 after resync incl. corpus parity (logs/feat-parity-post-r5wave.log) R5b ISSUES: 2 majors (fresh closure start failure; rejected or hung zero write) leave a fresh marker with TS guard off, ruled O24 | ACCEPTED via B5-r2 (R5c CLEAN) |
| SC-r3 | builder | $SCRATCH/wt/SC-r3 | e3faa83 (b625777) | skills + --check 0; full suite 254 OK; SC4 CLEAN (minors: pass-through definition only in architecture.md; no regression test for the three fixes, both to CL/morning report) | ACCEPTED (SC-r1..SC-r3 chain closed) |
| B9-r2 | builder-repair | $SCRATCH/wt/B9-r2 | e8c7380 (9c0d41c) | O22; 2 red then green + 2 controls; full suite 258 OK; R9c CLEAN (minors: repair refusal after stale BLOCKED -> design; O22 wording fixed in SPEC) | ACCEPTED |
| B2-r6 | builder | $SCRATCH/wt/B2-r6 | 1920442 (fc7c8cf) | O23; 9 corpus cases (5 red); plugin test 52/52 after merge (logs/feat-parity-post-r6wave.log); R2g CLEAN (minors: command-position skip list narrower than A5; quote-blind separator search) | ACCEPTED |
| B2-r7 | builder | $SCRATCH/wt/B2-r7 | c088b1b (5e62995) | O25; 12 corpus cases (7 red), no flips; full suite 258 OK; plugin test 59/59 after merge (logs/feat-parity-post-r7wave.log); R2h ISSUES: no defect introduced (160 twin pairs, 432-string TS/Python differential, 0 mismatches); two pre-existing fail-opens ruled O26 (double-quoted $(...)) and O27 (comment apostrophe), plus R2g minors O28 -> B2-r8 | ACCEPTED |
| B10 | builder | $SCRATCH/wt/B10 | d37d829 (50a89f8) | SPEC 12 acceptance tests named in report; full suite 320 OK in worktree; engine/integration/hooks/corpus/packaging 0 after merge | REPORTED; R10 pending |
| B5-r2 | builder-repair | $SCRATCH/wt/B5-r2 | 2db0fa5 (6c0e433) | O24 Python delegation; 6 red then green + 1 regression guard; plugin test 59/59; R5c CLEAN (payload contract checked against hooks.py with a real-hook probe) | ACCEPTED |
