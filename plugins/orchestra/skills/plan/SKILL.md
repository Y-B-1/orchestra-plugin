---
name: plan
description: "Rules for the planner: a short spec, a product options note, a type and signature sketch, and a ticket plan with dependencies. Load when you are the planner on a planned ask or on a large feature whose shape is a real choice. Not for builders, reviewers or investigators."
---
# Plan

- Write the spec in at most 40 lines: what changes, where, data shape, states, and how to check it. Do not write code in it.
- Read the code first. Use the project's glossary terms and respect decision records in the area.
- Ask first the questions that change the architecture, all at once, each with your recommended answer. A question that depends on another waits for the first answer. For rounds and recommended answers, load `orchestra:decide`.
- An open decision blocks only the work that depends on it. Say which work.
- Name shared resources beyond files: port, database, fixture, lockfile, build output. Units that share one run in order.
- Check each producer and consumer pair: unit B that reads unit A's output needs the same shape. Check the graph for cycles.
- Put the thinnest end-to-end slice first. Do prefactoring and removals before the slices that build on them.
- Choose test seams. Prefer an existing seam, the highest that works, and few of them. Give each one line on what it catches. A new seam is an open decision. Confirm the chosen seams with the owner (or list them under Decisions in a /goal run) before any test is written.
- Write acceptance criteria as numbered pass or fail checks, each run by a command or an observation. Never "works correctly".

## Product mode
Use it when the shape is a real choice, such as a new screen, a workflow or an interface others depend on.
- Give two or three options at concept level, one short paragraph each.
- Pick one and give the reason. Mark what the owner must confirm; a choice that changes behavior, scope, cost or risk is never yours alone.
- When the direction itself is unclear or the work is large, read `references/product.md` for the dossier.

## Sketch mode
When the change adds or reshapes types, interfaces or module boundaries, or the brief says sketch, read `references/sketch.md`. Write the caller's usage first, then the types and signatures with unimplemented bodies.

## Ticket mode
When the spec is approved and the work is more than one slice, or the brief says tickets, read `references/tickets.md`. Cut vertical slices with blocking edges, map the dependencies, group them into PRs and worktrees.

## Self-check
- Every requirement and acceptance criterion maps to a step or ticket.
- No placeholder (TODO, TBD, "etc."), no contradiction, no feature nobody asked for.
- Names and signatures agree across the plan.
- A plan several times longer than its spec has written the code. Cut it.
- A large plan gets an independent critic before any build starts.

Sources: mattpocock/skills@59db609 (to-spec, to-tickets, to-questionnaire), pstack@47c6f80 (architect), orchestra v2.15.3 (orchestra-design design, plan and product modes).
