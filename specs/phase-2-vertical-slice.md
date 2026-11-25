# Phase 2 — Vertical slice

**Goal:** the thinnest end-to-end path that is still real. A seeded profile goes through `search_jobs` (Get on Board), then `screen_batch` (LLM extraction + minimal eligibility in code, with claims), and ends as a shortlist in the terminal client and in Claude Code. Everything is tested with fakes, with CI and an eligibility eval harness.

**Scope decisions for this phase:**
- **Eligibility is minimal but real.** `job_extraction` uses the real LLM, and the three definitions of `system.md` §11.3 run in code, checking only location/country/region restrictions. Timezone, payroll, citizenship and hybrid checks come in phase 4.
- **The client is a minimal ReAct loop.** Commands and display come later.
- **Docker is built now.** `make up` works from day one, container problems show up early, and it is the same artifact phase 8 deploys. `make dev` stays for the daily loop.

**Order:** 2.1 → 2.13. Each task ends with its test passing and a small commit.

## Prerequisites
- [ ] OpenAI key in the real `.env`. Tasks up to 2.10 run on fakes; the key is needed from 2.11 (client demo) and 2.13 (eval).

## 2.1 Skeleton and tooling
- [x] `src/` layout from `CLAUDE.md` (only the folders this phase uses) and a `Makefile`. It starts with `setup`, `db`, `test`, `test-fast`, `lint`, `format`; the other targets (`dev`, `up`, `down`, `migrate`, `seed`, `client`, `eval`) arrive with the pieces they run.
- [x] ruff + pyright (basic) config, pytest-asyncio mode, ruff in pre-commit
- [x] `config/settings.py` (pydantic-settings, `ENV_FILE_PATH`, `SecretStr`), `config/constants.py`
- [x] `core/clock.py` (freezable `now()`), `core/errors.py` (domain errors with `error_code`), `core/logging.py` (JSON to stdout, no PII)
- [x] Tests: settings load from `.env.sample`; clock freeze

## 2.2 Database
- [x] SQLAlchemy 2 async models: `users`, `profiles`, `evidence`, `jobs`, `job_extractions`, `search_runs`, `run_jobs` (composite FK, index, statuses)
- [x] `db/session.py` (async engine, psycopg 3, `pool_pre_ping`); Alembic set up (synchronous engine, see `CLAUDE.md`); first migration
- [x] `db/startup.py`: migrations under a polled `pg_try_advisory_lock` (checkpointer `setup()` joins in phase 6)
- [x] `tests/conftest.py`: aborts unless the DB name ends in `_test`; transactional fixture (default) and committed + `TRUNCATE` fixture
- [x] Tests: migrations up/down/up; the composite FK rejects a mismatched `user_id`

## 2.3 Seeded profile
- [x] `scripts/seed_profile.py` (`make seed`), idempotent. It creates the `local` user and a complete sample profile (AR citizen, AR work authorization, remote, frontend/full-stack roles), plus evidence from `data/samples/sample_evidence.json` (language items are skipped until phase 3 adds CEFR columns). Sample data only.
- [x] Test: two runs leave one user, one profile and the same evidence

## 2.4 LLM layer
- [x] `llm/tasks.py` (`LLM_TASKS`, only `job_extraction`; stable prefix first in `llm/messages.py`) and `llm/openai_backend.py` (`ChatOpenAI`, Responses API, strict JSON schema, no `temperature`, effort `low`)
- [x] `llm.run()` (`llm/runner.py`): one retry with the validation error; usage summed over attempts and returned; automatic version hash (`llm/versioning.py`: prompt + examples + schema + model + params)
- [x] `models/job_facts.py` (`JobFacts` subset used now, in the shape validated in spike 1.5) and `app/jobs/verify.py` (quote and email verification)
- [x] `tests/fakes/fake_llm.py`: scripted per task; fails on unscripted calls; records calls
- [x] Tests: prompt assembly order; version hash changes with model/prompt/schema; FakeLLM rejects unscripted calls; quotes and `apply_email` kept only on an exact match
- [x] Real call verified once with `scripts/llm_smoke.py`: strict output valid, `prompt_cache_key` accepted, 1025 of 1028 input tokens cached on the second call

## 2.5 Get on Board adapter
- [x] Current endpoints, fields and terms verified
- [x] Shared `httpx.AsyncClient` with timeouts; `sources/base.py` (`JobSource` protocol, `SourceJob`), `sources/html_text.py` (HTML to plain text) and `sources/getonbrd.py` (normalize; one page at a time; backoff on 429; a source error becomes a warning); `sources/registry.py` picks recordings in demo mode
- [x] `scripts/record_fixtures.py` (Get on Board only): one raw page (30 jobs), JSON string values scrubbed, in `fixtures/sources/getonbrd/page-1.json`; replayed in `DEMO_MODE` with dates moved to now
- [x] Tests: respx with `assert_all_mocked=True`; normalization; source error → warning; PII test covers the new fixtures

## 2.6 `search_jobs` (basic)
- [x] The search runs these steps in order:
  1. `PROFILE_REQUIRED` if the profile is incomplete.
  2. Deterministic plan (roles × categories), stored in the run.
  3. Fetch from the source.
  4. Upsert `jobs` (`content_hash`, unique `(source, external_id)`).
  5. Keep only jobs that are new for the user.
  6. Prefilter: max age and closed only.
  7. Cap by recency; the rest count as `over_cap`.
  8. Create the `search_runs` row and `run_jobs` rows (`pending`, with positions).
- [x] Tests (integration): full path; a second search does not re-add the user's jobs
- [x] The caller owns the transaction: `tools/search_jobs.py` never commits, so a search is saved whole or not at all (the router commits in 2.9)

## 2.7 Minimal eligibility (code)
- [x] `app/eligibility/` with the three §11.3 definitions, location/country/region checks only, and a small `config/data/locations.py` (ISO countries; LATAM/Americas/Worldwide with ambiguity flags). Unknown profile value → `doubtful`. Disclaimer constant.
- [x] Unit tests:
  - explicit unmet → `not_eligible`
  - inferred only → `doubtful`
  - contradiction → `doubtful`
  - explicit LATAM for AR → `eligible`
  - no location signal → `doubtful`
- [x] Rules per restriction kind (phase 2): location is compared with the profile country; working hours are a warning; an ordinary contract type is a badge; explicit visa, citizenship, work authorization and US payroll phrases (W2, 1099, SSN) keep the job `doubtful` until phase 4 can compare them; hybrid/on-site jobs stay `doubtful` until phase 4 checks offices. An explicit location that excludes the country is `not_eligible` only when every place was understood
- [x] Free preview on the 15 hand-labelled spike postings (spike extractions, no LLM): 13/15 verdicts agree, **0 valid jobs `not_eligible`**. The 2 differences are the hybrid jobs (14 and 15), which phase 4 resolves with office data. "Work from anywhere" counts as a compatible location when nothing else excludes the user's country (user decision)

## 2.8 `screen_batch` (basic, with claims)
- [ ] Claims: up to `SCREEN_MAX_JOBS_PER_CALL` with `FOR UPDATE SKIP LOCKED`; stale `processing` rows reset using `:now`; claims released in `finally` when the call is cancelled
- [ ] Extraction with cache (`job_extractions` by job + version_hash + content_hash). Text is sanitized and capped at ~30k chars. The first call runs alone, the rest in parallel with `LLM_CONCURRENCY`, one DB session per task.
- [ ] Eligibility, then `done` with `screening_hash`. A failure is retried once; the second failure marks the job `failed`.
- [ ] Output: intermediate calls return progress only. The final call returns the shortlist (≤ 10 cards: eligibility, reason, quotes, disclaimer, apply link), discard counts and the `failed` count.
- [ ] Tests (committed fixture):
  - two concurrent calls never process the same job
  - a stale claim is recovered
  - cancellation releases its claims
  - a job failing twice ends `failed` and the run still finishes
  - a cached job costs 0 LLM calls

## 2.9 MCP server
- [ ] `server.py` `create_mcp_server()`: lifespan (engine, httpx), `strict_input_validation`, `mask_error_details`, `host_origin_protection`, `stateless_http` from settings
- [ ] `routers/tools.py`: `search_jobs(max_new: int = 30)` and `screen_batch(run_id: str)` with annotations and docstrings. Domain errors map to `ToolError` codes: `PROFILE_REQUIRED`, `RUN_NOT_FOUND`, `RUN_EXPIRED`.
- [ ] `/health` and `/ready` routes
- [ ] Contract tests (in-memory client): names, annotations, input schemas without `anyOf`, error shape
- [ ] E2E with fakes: search → screen (several calls) → shortlist; one source down

## 2.10 Docker
- [ ] `Dockerfile`: `python:3.14-slim` pinned by digest, uv, `uv sync --frozen --no-dev`, non-root user; entrypoint runs startup (migrations under the lock), then the server on `0.0.0.0:8000`
- [ ] `app` service in compose: `127.0.0.1:8000:8000`, waits for a healthy db, env file mounted read-only; `make up` / `make down`
- [ ] Verified: `make up` from scratch, `/health` OK, tools visible and callable from Claude Code (Windows → WSL `localhost`)

## 2.11 Minimal terminal client
- [ ] `client/`: FastMCP client (HTTP; in-memory in tests), MCP tools → LangChain tools, ReAct loop with `LLM_CLIENT_MODEL` through `llm/factory.py`, server `instructions` injected, shortlist printed
- [ ] Smoke test: the client starts, lists tools and runs one scripted turn with FakeLLM
- [ ] Demo with the real LLM: `make up && make seed && make client`, then "find me jobs" → shortlist

## 2.12 CI
- [ ] `.github/workflows/ci.yml`: actions pinned by SHA, Postgres service pinned by digest (same major), uv on `.python-version`; ruff, pyright, gitleaks, pip-audit, `make test`; no secrets

## 2.13 Eligibility eval harness
- [ ] `evals/run_eval.py --dataset eligibility --split dev|test --budget 0.50 [--no-cache]`, with an eval-only LLM cache and a budget guard (price table in `core/usage.py`, checked against current OpenAI prices)
- [ ] Metrics: precision/recall per class, **valid jobs marked `not_eligible` (must be 0)**, cost
- [ ] One run on **dev**, result recorded here; the test split waits for a milestone

## Out of scope (later phases)
- **Phase 3:** CV upload and profile tools.
- **Phase 4:** SerpApi, cross-portal dedupe, LLM planner and replan, role-family prefilter, timezone/payroll/citizenship tables, hybrid/GeoNames.
- **Phase 5:** matching, and the other tools, prompts and resources.
- **Phase 6:** decisions, drafts, LangGraph checkpointer.
- **Phase 7:** full Opik.
- **Phase 8:** auth, limits, Azure CD.

## Definition of done
- [ ] `make test` green (unit, integration, contract, e2e, client smoke) on `laburo_test`; `make lint` clean
- [ ] CI green on the PR
- [ ] `make up` → `make seed` → `search_jobs` → `screen_batch` → shortlist, working from the terminal client **and** from Claude Code (output shown)
- [ ] Eligibility eval on dev: 0 valid jobs `not_eligible`; result recorded here
- [ ] New decisions as one line in `CLAUDE.md`; `system.md` updated only where a contract changed
- [ ] PR to `main`; **Current phase** → 3

Stopped at: 2.8a done (claim_jobs, release_claims, committed DB fixture). Next: 2.8b extraction with cache; the `finally` that releases claims on cancel lands with the tool in 2.8c.
