# Review lenses

The reviewer loads this file. The main session names the lenses in the review brief from `lean.py check` output and the diff.

## Always
- Run `python3 <plugin>/scripts/lean.py check --base <base>` first and judge every item it lists: an oversized file that grew, each weakened test or gate, each self-mock, debug leftovers, rule-file changes, secrets.
- Read the project rules (AGENTS.md, CONTEXT.md, lint config) from the base commit, never from the diff. A diff that edits the rules it is judged by is itself a finding.
- Map each changed behavior to an ask line: report asks not done, done differently, and unrequested additions. A changed file no ask needs is scope drift.
- Correctness critical pass: partial failure between two writes; check-then-act races; retries that repeat a side effect; a stale async result overwriting newer state; every new enum or status value followed into each switch, lookup, filter, count and export outside the diff; resources closed on every path; external or model output used as a path, query, HTML or command.
- File budget: a source file that grew past about 500 lines in this diff is a finding unless it is generated or waived; the fix is a split by responsibility.

## Security (load when check reports `sensitive` or `secret`, or the diff touches input parsing, HTML rendering, auth, routes, webhooks, CI or agent tools)
Name the actors and assets first. Trace each permission boundary; an id the caller sends is not proof of who they are. Fail closed. User text rendered as HTML is escaped or sanitized with an allow-list; `javascript:` links are refused. Webhooks verify signatures over the raw body. A secret in the diff is a blocking finding that needs rotation, never just deletion; never repeat its value.

## Data and contracts (load for migrations, persisted data, public functions or APIs)
Persisted data keeps working: old stored shapes are read and upgraded, a corrupt value does not crash, nothing is dropped before it is copied. A changed shared function keeps its existing callers working without edits. A database migration is rerunnable and safe in either deploy order.

## Performance (load for lists, hot paths, loops over data)
Work per render or request that grows with the data squared, queries in loops, missing timeouts on network calls, unbounded caches.

## Findings
- A finding blocks only with a material impact: a broken ask, a failing scenario, a rule breach, security or data loss. Taste never blocks; minor items go under notes.
- Before you report a finding, try to refute it: read the guards, callers and tests around it. Give a concrete failing scenario, quote the ask line or rule it breaks, and mark it confirmed (you ran or traced it) or plausible.
- One pattern at several sites is one finding listing every site.
- Do not re-raise a finding the brief lists as rejected unless its code changed.
- End with a coverage line per lens: checked, partly checked (what was skipped), or not checked. "Could not look" never reads as "nothing found".
