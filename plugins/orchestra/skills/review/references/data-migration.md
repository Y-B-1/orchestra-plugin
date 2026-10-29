# Data migration lens

Use when the diff changes a stored shape, a schema or a backfill.

- Real size: the migration runs on a table of production size without a long lock or full rewrite. Name the table size you assumed.
- Twice: it can run again after a partial run and converge.
- Order: code and schema both work during deploy in either order (new code on old schema, old code on new schema).
- Rollback: a way back exists, and it does not lose data written since.
- Backfill: batched, resumable, throttled. Nothing is dropped or overwritten before it is copied and checked.
- New required column or constraint: existing rows satisfy it, or a default and a backfill come first.
- New index on a hot table: built without blocking writes where the database allows.
- Old readers: stored data in the old shape is read by new code, or migrated first. Every other reader of that data (jobs, exports, other services) is named.
- Destructive step (drop, truncate, delete): a separate later step after the new path is proven.
- Test with old-shape data, not only empty fixtures.
