---
paths:
  - "tests/**"
  - "evals/**"
  - "fixtures/**"
---

# Testing rules

- Tests never call real APIs: `FakeLLM` fails on any unscripted call; respx with `assert_all_mocked=True`.
- Real Postgres in tests, never SQLite, and always the separate `laburo_test` database. `conftest.py` aborts if the database name does not end in `_test`.
- Two DB fixtures:
  - **transactional** (default): one transaction per test, rolled back;
  - **committed**: real commits and `TRUNCATE` after the test, for concurrency, claim and lease tests, which need two connections that see committed data.
- Time is frozen through `core.clock`; SQL receives `:now` as a parameter, so stale claims and expired leases are controllable.
- Cost guards are tests: a repeated requirement is linked once, a cached job costs 0 LLM calls.
- Concurrency is tested: two simultaneous `screen_batch` calls never process the same job; a stale profile preview is rejected; a second draft request while one runs does not start another execution.
- Tenant isolation is tested with two users, including private pasted jobs.
- Fixtures from real postings are scrubbed (`make scrub-fixtures` / `make record-fixtures`): contact emails, phone numbers and contact names become placeholders (`contact@example.com`). A test fails if `fixtures/` contains an email outside `example.com` or a phone number. Raw captures stay outside the repo. Company names and posting text may stay.
- GeoNames in tests: load a small subset into `geo_places`, never the full snapshot.
- LangGraph checkpointer tests use their own psycopg connection; clean up threads after each test.
- Evals run manually only, with a default budget of $0.50 per run (`--budget` overrides) and an eval-only LLM cache (`--no-cache` for design experiments). Tune on the dev split; run the test split only at milestones.
