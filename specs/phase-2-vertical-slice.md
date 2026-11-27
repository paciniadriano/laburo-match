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
  5. Keep only jobs the user has not judged: a job an earlier run left `pending` (or abandoned `processing`) moves to the new run and counts as `carried_over`.
  6. Prefilter: max age and closed only.
  7. Cap by recency; the rest count as `over_cap`.
  8. Create the `search_runs` row and `run_jobs` rows (`pending`, with positions).
- [x] Tests (integration): full path; a second search does not re-add jobs the user already judged; unfinished jobs are carried over and wait in one run only
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
- [x] Claims: up to `SCREEN_MAX_JOBS_PER_CALL` with `FOR UPDATE SKIP LOCKED`; stale `processing` rows reset using `:now`; claims released in `finally` when the call is cancelled
- [x] Extraction with cache (`job_extractions` by job + version_hash + content_hash). Text is sanitized and capped at ~30k chars. The first call runs alone, the rest in parallel with `LLM_CONCURRENCY`, one DB session per task.
- [x] Eligibility, then `done` with `screening_hash`. A failure is retried once; the second failure marks the job `failed`.
- [x] Output: intermediate calls return progress only. The final call returns the shortlist (≤ 10 cards: eligibility, reason, quotes, disclaimer, apply link), discard counts and the `failed` count.
- [x] Tests (committed fixture):
  - two concurrent calls never process the same job
  - a stale claim is recovered
  - cancellation releases its claims
  - a job failing twice ends `failed` and the run still finishes
  - a cached job costs 0 LLM calls

## 2.9 MCP server
- [x] `server.py` `create_mcp_server()`: lifespan (engine, httpx), `strict_input_validation`, `mask_error_details`, `host_origin_protection`, `stateless_http` from settings
- [x] `routers/tools.py`: `search_jobs(max_new: int = 30)` and `screen_batch(run_id: str)` with annotations and docstrings. Domain errors map to `ToolError` codes: `PROFILE_REQUIRED`, `RUN_NOT_FOUND`, `RUN_EXPIRED`.
- [x] `/health` and `/ready` routes
- [x] Contract tests (in-memory client): names, annotations, input schemas without `anyOf`, error shape
- [x] E2E with fakes: search → screen (several calls) → shortlist; one source down

## 2.10 Docker
- [x] `Dockerfile`: `python:3.14-slim` pinned by digest, uv, `uv sync --frozen --no-dev`, non-root user; entrypoint runs startup (migrations under the lock), then the server on `0.0.0.0:8000`
- [x] `app` service in compose: `127.0.0.1:8000:8000`, waits for a healthy db, real `.env` injected with `env_file` (a bind mount keeps the host's 0600 mode, which the container user cannot read); `make up` / `make down`
- [x] Verified: `make up` from scratch, `/health` OK, tools visible and callable from Claude Code. Real run through the container, 30 Get on Board jobs (demo fixture): 30 `done`, 0 errors, 30 LLM calls, 40,839 input / 6,079 output tokens; verdicts 1 eligible, 29 doubtful, 0 not_eligible

## 2.11 Minimal terminal client
- [x] `client/`: FastMCP client (HTTP; in-memory in tests), MCP tools → LangChain tools, ReAct loop with `LLM_CLIENT_MODEL` through `llm/factory.py`, server `instructions` injected, shortlist printed
- [x] Smoke test: the client starts, lists tools and runs one scripted turn with FakeLLM
- [x] Demo with the real LLM: `make up && make seed && make client`, then "find me jobs" → shortlist (30 jobs, 2 screen calls, 10 cards printed with Get on Board links, summary in the user's language; 15 of the 30 jobs were hybrid and `doubtful`, see 2.13)

## 2.12 CI
- [x] `.github/workflows/ci.yml`: actions pinned by SHA, Postgres service pinned by digest (same major), uv on `.python-version`; ruff, pyright, gitleaks, pip-audit, `make test`; no secrets

## 2.13 Eligibility eval harness
- [x] `evals/run_eval.py --dataset eligibility --split dev|test --budget 0.50 [--no-cache]`, with an eval-only LLM cache and a budget guard (price table in `core/usage.py`, checked against current OpenAI prices)
- [x] Metrics: precision/recall per class, **valid jobs marked `not_eligible` (must be 0)**, cost
- [x] One run on **dev**, result recorded here; the test split waits for a milestone
  - **2026-11-27, `gpt-6-luna`, version `5f51ace8d0e3`, posting text as the server serves it: 8/10, 0 valid jobs `not_eligible` (gate PASS), $0.0028.** `eligible` 4/4; `doubtful` 3/3 (precision 60%); `not_eligible` 1/3. Both misses go the cautious way (expected `not_eligible`, got `doubtful`), so no valid job was lost:
    - job 14: hybrid. The server never shows the model the aggregator's `countries=['Chile']`; the office check is phase 4.
    - job 01: the model wrote the place as "cualquier estado de USA" and the resolver did not know the Spanish "cualquier" (fixed next to a known country, with tests). Re-measured: **9/10, $0.00 (10 cache hits)**; only job 14 is left.
  - A first run that fed the model the fixtures' aggregator metadata gave 10/10. It is void: the product never shows that metadata.
  - Caveats: dev is the split the rules were tuned on, and n=10 (one item is 10 points). The held-out test split (5 items) is still unrun.

## 2.14 Office abroad (added after the 2.11 demo)
Found in the demo: 21 of 30 jobs were hybrid or on-site in Chile and took 6 of the 10 cards. The rule was already decided in `CLAUDE.md`; only its office/distance part needs phase 4.
- [x] Get on Board's declared modality stored in `jobs.modality` (migration); `remote_local` → `remote`
- [x] Prefilter `office_abroad` before the cap, no LLM: hybrid/on-site, every declared country known and not the user's, and the prose names no place that may include it (`core/places.mentions_area`)
- [x] The places resolver moves to `core/` (search and eligibility both use it)
- [x] The eval runs the same prefilter on the fixtures' source fields; the client shows what was left out and why
- [x] Offline check (code only, no LLM) on dev: the prefilter removes job 14 only, labelled `not_eligible`
- [ ] `make eval` on dev with the prefilter: expected 10/10, $0 (cached)
- [ ] Demo: `make up`, empty the runs, `make client`: no hybrid/on-site abroad in the shortlist
- Note: the `remote_local` choice was checked on dev job 04 and on test job 09, so the test split is no longer fully untouched for that rule. That choice was later found wrong and replaced in 2.18.

## 2.15 Search everything (user decision: a job seeker wants every job they can apply to)
- [x] `MAX_NEW_JOBS_PER_SEARCH` becomes a safety limit (300); `search_jobs(max_new=300)` queues every job that passes the filters, most relevant first
- [x] Prefilter `duplicate`: same employer, title and place inside one search keeps the newest; no employer name, no merge
- [x] `make record-fixtures` records every page of the category (50 jobs per file, under the 1 MB hook); the demo replays all pages in order, a job on two pages kept once
- [ ] The user runs `make record-fixtures` (free) and commits the new pages

## 2.16 Time-boxed screening rounds (user decision: first results within ~30 s)
- [x] `screen_batch` = one round of `SCREEN_ROUND_SECONDS` (20): a pool of `LLM_CONCURRENCY` workers, most relevant first, each verdict saved at once; at the deadline in-flight jobs go back to the queue without counting an attempt
- [x] Every round returns the best jobs judged so far (`partial` / `done`); the host shows them and continues only if the user asks (server instructions, hints, client rules)
- [x] `SCREEN_MAX_JOBS_PER_CALL` becomes a safety limit (300); the run's funnel stores `screen_ms`; the client prints how long each answer took
- [x] Tests: the round stops at its budget and releases unfinished jobs uncounted; cached jobs all fit in one round with a slow model; first job alone, then at most N workers; safety limit; retry inside the round; cancellation still releases claims
- [ ] Measured: first search on the full recording, wait in seconds, `screen_ms`, and jobs judged in the first round; tune `LLM_CONCURRENCY` from it

## 2.18 What Get on Board declares (found in the 2.17 demo: 26 remote jobs "said nothing about where")
- [x] The API is asked for `location_tenants` names; `jobs.residence_text` (migration): `anywhere` for `fully_remote`, the countries for `remote_local`
- [x] Prefilter `residence_abroad`: remote only for people in other countries (same prose guard as `office_abroad`)
- [x] Eligibility weighs the declared policy as explicit evidence (`app/eligibility/declared.py`): fully remote → eligible unless the text asks for what no one abroad can meet; residence or office abroad → not eligible, or doubtful when the text says otherwise; the cards cite the source
- [x] "1099 contractor" becomes a badge with a W-8BEN note (user decision, after checking tax guides)
- [x] Dev labels 08 and 11 relabelled `eligible` (both fully remote; user decision, noted in the dataset)
- [x] Offline check from the eval cache (no provider allowed): dev 10/10, 0 valid jobs `not_eligible`, 9 cache hits, 0 calls
- [x] Audit of the deterministic discards on live data (2026-11-28, 289 jobs; the prefilter would remove 147 `office_abroad` and 34 `residence_abroad`, and open 62 as fully remote): a random sample of 12 + 12 + 4 checked against each job page's own remote work policy, **28/28 agree**, no page names Argentina or Latin America as open. Zero errors in 24 discards still allows a rate up to about 12 % (rule of three), so the audit is repeated when a rule changes
- [x] `DEMO_MODE` verified: it only switches Get on Board between recording and live API (no SerpApi path exists); a live fetch parsed 289 jobs with no warnings and residence declared for 123 of 130 remote ones
- [x] The user re-recorded (289 jobs, residence declared for 123 of 130 remote) and ran the demo live (`DEMO_MODE=false`): 53 to screen, all judged in one round, first answer in 19 s; 37 eligible, 0 doubtful, 16 not eligible; left out 137 too old, 85 office abroad, 14 remote only for other countries
- [x] Found in that demo: Niuro's "Mexico only" postings say "flexibility in work location globally"; first made doubtful through the prose guard, then decided by the user in 2.19: the employer's policy wins
- [ ] Check once in Claude Code that a `partial` round waits for the user instead of chaining rounds on its own

## 2.19 The employer's policy decides; useful cards first (user decisions after the live 2.18 demo)
- [x] A declared residence or office only in other countries rules the job out whatever the text says (prefilter and screening); the prose guard (`mentions_area`, `OPEN_PLACE_PHRASES`) is removed
- [x] Shortlist and `list_jobs` order: eligible first, then title relevance to the target roles (stand-in for the fit band until phase 5), then the newest; `title_relevance` moves to `core/`
- [x] Tests: the policy wins over a "work globally" blurb; the closest title comes before the newest

## 2.17 `list_jobs`, read-only (user decision A)
- [x] `list_jobs(status: Literal["all","filtered"] = "all", limit: int = 20, offset: int = 0)`: the user's latest verdict per job across runs, eligible first; `filtered` shows prefilter and `not_eligible` discards with a readable reason; `stale` when the profile changed; pages of at most 50
- [x] Contract, isolation between users, paging, stale marker and filtered-reason tests; the client prints listings itself
- Replaces the earlier limitation (jobs beyond the 10 cards could not be opened until phase 6).

## Known limitation: verdicts do not notice rule changes
A verdict is marked `stale` only when the profile changes (`screening_hash`). A change of rules, or of what the source declares about a job, leaves old verdicts as they were, and judged jobs count as already seen in later searches. Accepted while the rules are being stabilized (user decision): after a rule change, reset with `TRUNCATE run_jobs, search_runs CASCADE` (extractions stay cached, so re-screening costs almost nothing). **Must be fixed before data that cannot be thrown away exists**: saved decisions (phase 6) or other users; the fix is a rules version plus the declared fields inside the verdict fingerprint.

## Out of scope (later phases)
- **Phase 3:** CV upload and profile tools.
- **Phase 4, before the second source** (from the Get on Board coupling review): `SourceQuery.categories` and the plan's fixed `programming` / `getonbrd` / "Searched Get on Board" become a per-source query; `location_text` is read as office countries by the prefilter and screening, so an explicit `office_countries` field replaces that reading; the `"anywhere"` value of `residence_text` becomes a typed field; the eligibility eval stores neutral declared fields per item instead of parsing the spike fixture header; split `DEMO_MODE` per source.
- **Phase 4:** the planner must map target roles to Get on Board categories (phase 2 always searches `programming`, so AI roles never fetch AI jobs); Google Jobs declares no modality, so the office-country rule must also run at screening for its jobs (see `system.md` §9 note); the 300 safety limit and `SEARCH_FETCH_LIMIT` apply to the merged pool, so paid SerpApi results must get their own room (queued first or a per-source share) and never land in `over_cap`, where the credits they cost would be wasted; SerpApi, cross-portal dedupe, LLM planner and replan, role-family prefilter, timezone/payroll/citizenship tables, hybrid/GeoNames.
- **Phase 5:** matching, and the other tools, prompts and resources.
- **Phase 6:** decisions, drafts, LangGraph checkpointer.
- **Phase 7:** full Opik.
- **Phase 8:** auth, limits, Azure CD; a global limit on simultaneous LLM calls across users (each `screen_batch` round runs `LLM_CONCURRENCY` workers, so several users at once multiply them and hit the provider's rate limit).

## Definition of done
- [ ] `make test` green (unit, integration, contract, e2e, client smoke) on `laburo_test`; `make lint` clean
- [ ] CI green on the PR
- [ ] `make up` → `make seed` → `search_jobs` → `screen_batch` → shortlist, working from the terminal client **and** from Claude Code (output shown)
- [ ] Eligibility eval on dev: 0 valid jobs `not_eligible`; result recorded here
- [ ] New decisions as one line in `CLAUDE.md`; `system.md` updated only where a contract changed
- [ ] PR to `main`; **Current phase** → 3

Stopped at: 2.19 done (389 tests). Left: `make eval`, the Claude Code check of partial rounds; phase close and PR wait for the user.
