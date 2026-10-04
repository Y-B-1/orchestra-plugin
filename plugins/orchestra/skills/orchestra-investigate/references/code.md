Source: derived from obra/superpowers@8ca22dba9a94 skills/systematic-debugging/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/diagnosing-bugs/SKILL.md (MIT); garrytan/gstack@4015c2870b06 investigate/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-investigate/references/code.md

# Investigator: code mode

Answer the narrow question from source. The brief decides the path: a question to answer is source discovery, and a defect to diagnose is bug diagnosis.

## Source discovery

Search for the files and symbols the question names, then follow callers, data flow and tests that exercise them. Read the code, not the comments about it. Report exact paths and symbols, each with its evidence label. Make no edit and propose no fix unless the brief asks for one. If the brief describes a defect, use the diagnosis path below instead.

## Bug diagnosis

Find the cause before naming any fix. A fix aimed at a symptom hides the cause and makes the next bug harder to find. Build the pass/fail loop first; with no loop, report `STATUS: BLOCKED`.

### 1. Build a feedback loop first

Read the project glossary and any decision records for the area. Check recent changes to the affected paths: a regression puts the cause in the diff.

Then build a pass/fail loop that goes red on this bug. Do not read code for a theory before it exists. Try these in order:
1. a failing test at the seam that reaches the bug;
2. a request script against a running dev server;
3. a command-line run on a fixture, diffed against known-good output;
4. a headless browser script asserting on DOM, console or network;
5. a replay of a captured payload or log through the code path;
6. a throwaway harness around one function with mocked dependencies;
7. a property or fuzz loop for sometimes-wrong output;
8. a bisection harness when the bug appeared between two known states;
9. a differential run of old against new, or of two configs.


The loop is done when one command, already run, is red-capable (it asserts the reported symptom, not "does not crash"), deterministic, fast and runnable unattended. For a flaky bug, raise the reproduction rate until it is debuggable. If you cannot build a loop, stop with `STATUS: BLOCKED`. List what you tried and name what you need: access to the failing environment, a redacted captured artifact, or approval for temporary instrumentation.

### 2. Reproduce and minimise

Confirm the loop shows the failure the brief describes, not a neighbouring one. Capture the exact symptom. Then cut inputs, callers, config and steps one at a time, rerunning after each cut. Stop when removing any remaining element turns the loop green.

### 3. Rank hypotheses

Write 3 to 5 hypotheses before testing any. Each states its prediction: "If X is the cause, changing Y removes the bug." A hypothesis without a prediction is discarded or sharpened.

### 4. Test one at a time

Change one variable per probe, and map each probe to a prediction. Prefer a debugger or REPL inspection; otherwise add targeted logs at the boundaries that separate the hypotheses, never "log everything". Tag probe output with a unique prefix such as `[DEBUG-a4f2]` so none survives.

For a failure deep in a call chain, trace backward: where does the bad value originate, and what passed it in? Stop at the source, not the symptom. Across component boundaries, record what enters and leaves each one, then investigate the failing layer. Compare against similar working code and list every difference. For a performance bug, take a baseline measurement first, then bisect.

Three disproved hypotheses means stop. Report the pattern as a design question (shared state, coupling, a fix that needs wide change) with what you tried. Do not start a fourth.

### 5. Report

For bug diagnosis the report body is a debug report, under the lines the worker contract requires:
- Symptom: what was observed.
- Root cause: what is wrong, separated from the symptom, with evidence labels.
- Proposed fix: file and line. You make no edit.
- Evidence: the loop command, its redacted output and exit, and the ranked hypotheses with the result of each probe.
- Regression check: a description of the failing behavior test, at a seam that exercises the real call pattern. If no such seam exists, say so; that is a finding about the code.
- Blast radius: the files a fix would touch. Flag it when a fix touches more than 5 files so the coordinator can decide.
- Related: earlier bugs and rules that apply.
