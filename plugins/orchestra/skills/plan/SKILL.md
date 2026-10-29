---
name: plan
description: "Gives the rules for writing a short spec and, when the shape is a real choice, a product options note. Load when you are the planner. Not for builders, reviewers or investigators."
---
# Plan

- Write the spec in at most 40 lines: what changes, where, data shape, states, and how to check it.
- Ask first the questions that change the architecture. Ask them all at once, each with your recommended answer.
- Do not ask what the code can answer. Read the code first.
- A question that depends on another waits for the first answer.
- An open decision blocks only the work that depends on it. Say which work.
- Name shared resources beyond files: port, database, fixture, lockfile, build output. Units that share one run in order.
- Check each producer and consumer pair: unit B that reads unit A's output needs the same shape. Check the graph for cycles.
- Put the thinnest end-to-end slice first. Do removals and prefactoring before the slices that build on them.
- Do not write code in the spec.

## Product mode
Use it when the shape is a real choice, such as a new screen, a workflow or an interface others depend on.
- Give two or three options at concept level, one short paragraph each.
- Pick one and give the reason.
- Mark what the owner must confirm. A choice that changes behavior, scope, cost or risk is never made by you alone.
- Write a decision record only for a choice that is hard to reverse.

Sources: orchestra v2.15.3, mattpocock/skills@59db609, cursor/plugins pstack@c742dd6.
