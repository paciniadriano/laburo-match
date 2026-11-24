# Fixtures

Recorded inputs shared by tests, evals and demo mode. `postings/getonbrd/` holds 15 tech postings from the public
Get on Board API, captured in November 2026 for spike 1.5, as plain text. Contact data is removed with
`scripts/scrub_fixtures.py` and `tests/unit/test_fixtures_pii.py` fails if any email outside example.com or phone remains.
