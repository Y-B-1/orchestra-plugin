# Statechart for a flow

Use before you build or test a flow with many states and events. Failure it prevents: an event nobody handled in some state (a payment callback after cancel, a double submit, sync after logout).

## Steps
1. List the states in the owner's words ("Paying", "Lease held, write pending"), not variable names. Include every end state and every error state.
2. List the events: user actions, timeouts, retries, callbacks, remote messages, crashes. Include events that arrive late or twice.
3. Write the table, one row per (state, event):

   | State | Event | Guard | Next state | Side effect |
   | --- | --- | --- | --- | --- |

4. Check the table:
   - Every non-final state has at least one exit.
   - Every event has a row in every state. A cell with no row is a gap: decide "ignore", "reject" or a real transition, and write it. Never leave it blank.
   - Two rows with the same state and event have guards that cannot both be true, and together cover every case.
   - Every end state is reachable, and no state is reachable that the owner did not name.
5. Write each rule the owner agrees to as an invariant ("a paid order never returns to cart", "one booking per slot") and check it holds on every row. Never weaken a rule to make it hold.
6. Show the table to the owner when a gap needs a product decision. Ask all gaps in one round, each with your recommended answer. In a /goal session, decide, log it, proceed.
7. Derive tests: one per transition that matters (money moves, data is written or lost, the user sees a new screen), one per gap decision, one per invariant. Name each test by state, event and expected next state. Skip transitions that only repeat another.
8. Build from the table. Make the code's state a single value or an enum, and make an illegal event a visible, tested outcome, not a silent return.
9. Keep the table in the repo next to the code. Update it in the same change as the flow.

## When the model is too large to check by hand
Split independent parts into parallel regions (playback and volume). When states pass a few dozen, or an ordering bug is likely (concurrency, retries), write a model with a checker such as TLA+ with TLC and replay each counterexample path against the real code as a test. If the bug does not reproduce, treat the model as wrong until shown otherwise. Formal checking is optional. The table check in step 4 is required.
