# Spike 1.2 — Docker + Postgres + Alembic + checkpointer

**Verdict: GO**, with one design correction (advisory lock must be polled, see below).

| Threshold | Measured |
|---|---|
| Postgres major = highest supported by Azure Flexible Server | 18 (18.7), image pinned by digest. Microsoft docs list up to 18 (standard support to Nov 2030); the Azure CLI reference also mentions 19 without explanation. Re-confirm in spike 1.8 |
| Compose healthy in < 30 s | 3 s |
| `laburo` and `laburo_test` created by init script | Yes (`docker/postgres/init-databases.sql`; runs only on an empty volume) |
| Alembic up/down/up | Works on a dummy table; `alembic check` reports no changes |
| Autogenerate ignores checkpointer tables | Only with `include_object` filter. Without it Alembic proposes `drop_table` for all 4 checkpointer tables and their indexes |
| `setup()` after Alembic under one advisory lock | Two simultaneous starts on an empty DB: both succeed, work runs once, serialised |

## Findings
- **Volume:** `down` keeps data, `down -v` wipes it. Postgres 18 images mount the data volume at `/var/lib/postgresql` (not `/var/lib/postgresql/data`).
- **Deadlock found:** a blocking `pg_advisory_lock()` keeps a statement open. The lock holder's checkpointer `setup()` runs `CREATE INDEX CONCURRENTLY`, which waits for every open statement, including the waiter's. Postgres does not detect it; both hang forever. **Fix:** poll with `pg_try_advisory_lock()` plus a short sleep, so waiters hold no open statement. Implemented in `startup.py`; carry this into the real startup routine.
- Checkpointer tables to exclude from Alembic: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`.
- Plan B (separate schema for the checkpointer) was not needed.
