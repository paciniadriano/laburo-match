# laburo-match — System specification

Status: v1 design, before implementation. Decisions and their reasons live in `CLAUDE.md`; this document describes **what** the system does. Items marked **[verify]** depend on third-party facts (model names, prices, limits, library versions) and must be confirmed during the spikes. Naming follows the job identity rules in `CLAUDE.md`: a job posting is a `job`.

---

## 1. Overview

**Problem.** Many postings say "Remote" but hide restrictions (US-only, work authorization, US hours, payroll in another country), and hybrid or on-site postings may be too far away. Candidates waste time reading postings they cannot take, and job boards rarely tell them how well they fit or how to present their experience.

**Solution.** An MCP server that:
1. Searches jobs in public sources based on the user's profile.
2. Estimates, per job, whether the user can apply **from their location** (`eligible` / `not_eligible` / `doubtful`), with the exact quotes that support the verdict. It is an estimate, not legal advice.
3. Measures fit requirement by requirement, with evidence from the user's CV and their own statements, and explains gaps and how to argue them.
4. Lets the user ask questions about a job and get answers backed by verified quotes.
5. Drafts a tailored cover letter, CV bullets and screening answers in the job's language, without inventing verifiable facts.

**Target user.** Professionals looking for remote, hybrid or on-site jobs, in any country.

---

## 2. Scope

### In v1
- **Tech roles**: sources, search planner, fixtures and evals are tech-focused. The architecture is domain-agnostic; other domains only need new evals.
- Profile from a PDF CV + conversation; hard constraints, soft preferences, exclusions, writing style.
- Modalities: remote, hybrid, on-site (hybrid/on-site is the last, decoupled block of phase 4).
- Sources: Google Jobs (via SerpApi) and Get on Board; any other posting is pasted as text into `analyze_posting`.
- Search planning (LLM, validated, one replan), deduplication across portals, profile-aware prefilters.
- Eligibility (location, authorization, citizenship, timezone, contract, modality/distance), fit with evidence, gaps and profile questions aggregated across jobs.
- Q&A about jobs with verified quotes.
- Decisions and pipeline status (saved → applied → interviewing → rejected/offer), learned exclusions.
- Draft workflow (LangGraph) with evidence check, LLM review, human feedback.
- Terminal MCP client (ReAct), project skill, MCP prompts.
- Evals, Opik observability, Docker, CI, Azure deploy with auth (phase 8).

### Out of v1 (roadmap)
- Scheduled daily search with email digest (Azure Container Apps Jobs).
- Server-side fetching of posting URLs (hosts with web tools can read pages themselves); `research_company` (Tavily search + orchestrator-workers).
- Remotive and other sources whose API terms do not fit a multi-user server.
- Multiple profiles per user (e.g. frontend vs AI CVs).
- Short per-user job numbers ("#47") instead of run-scoped positions.
- Interview preparation from job + gaps.
- OCR / vision for scanned CVs; DOCX CVs.
- FastMCP 4 upgrade.
- Ranking by source quality; SBOM and image scanning (optional in phase 8).
- Embeddings, salary benchmarks, auto-apply (never).

---

## 3. Course compliance checklist

| Requirement | Where it is met |
|---|---|
| FastMCP in Python | `src/server.py` |
| ≥ 1 meaningful tool | 12 tools (§12) |
| ≥ 1 MCP prompt with an agentic workflow and a user feedback step | `review_jobs`, `setup_profile` (§12.3) |
| Public GitHub repo | `github.com/paciniadriano/laburo-match` |
| `uv init --python 3.14.0 .` | Phase 0 |
| Organized structure (`src/server.py`, `src/routers/…`, `src/tools/`, `src/app/`, `src/core/` as utils, `src/config/settings.py` with pydantic-settings) | Repository layout in `CLAUDE.md` |
| README from the template, all placeholders replaced: description, setup (clone, uv, env vars, run), env vars and API keys, Cursor JSON config, required features, custom features | Phase 9 |
| No API keys or credentials in the project folder or the repo; `.env.sample` with fake values | `.env` outside the repo via `ENV_FILE_PATH` |
| ≥ 4 custom features | MCP client app, third-party APIs, resources, workflow patterns, advanced agentic pattern, memory, HITL generation→validation, Opik, eval with 20–30+ samples and LLM judge, custom data, CI/ruff/Docker, Descope auth, DB + docker-compose, cloud deploy, structured outputs |
| Submission `.txt` with `GitHub Repository: https://github.com/...` | Phase 9 |
| Course lesson 35: deliberate allocation MCP / skill / CLI | README section "Capability channels" (§4) |

---

## 4. Hosts and capability channels

| Channel | What it provides here |
|---|---|
| **MCP server** (abilities) | Tools, resources and prompts: search, screening, Q&A, decisions, drafts |
| **Skill** (procedure) | `.claude/skills/laburo-match/SKILL.md`: entry point ("find me jobs"), fetches the workflow via `get_workflow_instructions` and follows it |
| **CLI** (existing binaries) | `uv`, `docker compose`, `make`, `git`, `gh` — never wrapped in tools |

| Host | Connection | Entry point |
|---|---|---|
| Terminal client (`client/`) | in-memory (dev, evals) or HTTP | `/prompt/review_jobs`, `/prompt/setup_profile` |
| Claude Code | `.mcp.json` (`type: http`, `http://localhost:8000/mcp`) | Skill (auto) or prompts as slash commands |
| Cursor | `"url": "http://localhost:8000/mcp"` (README JSON block) | Ask in chat; prompts if supported |
| Claude Desktop | Local: `npx mcp-remote http://localhost:8000/mcp` (Node on Windows) or the `fastmcp-remote` bridge; remote: custom connector with the Azure URL | Skill uploaded as zip, or prompts from the "+" menu |

- Windows hosts reach the server running in WSL2 or Docker through `localhost` (checked in spike 1.3).
- Claude Desktop installed from the Microsoft Store keeps its config in `%LOCALAPPDATA%\Claude-Data\<package>\claude_desktop_config.json`, not in `%APPDATA%\Claude` (checked in spike 1.3); quit it from the tray before editing. Other people should use the remote custom connector (public HTTPS URL), not the local JSON route.
- Links: the server never fetches posting URLs. If the user shares a link, the host reads the page with its own web tools (when it has them) and passes the text to `analyze_posting`; for blocked sites (`config/data/known_sites.py`: LinkedIn, Bumeran, ZonaJobs, Computrabajo, Indeed) the host asks the user to paste the text.

---

## 5. Architecture

```
Host (client / Claude Code / Cursor / Claude Desktop)
        │  MCP over Streamable HTTP (in-memory for tests)
        ▼
FastMCP 3.x server ── routers → tools → app (logic)
   │        │            │
   │        │            ├── sources/ (SerpApi, Get on Board)
   │        │            ├── llm/ (LLM_TASKS registry → ChatOpenAI → OpenAI Responses API)
   │        │            ├── geo/ (geo_places lookup + distance)
   │        │            └── drafting/ (LangGraph functional workflow + Postgres checkpointer)
   │        └── custom routes: /upload, /health, /ready
   ├── PostgreSQL (SQLAlchemy async + psycopg 3, Alembic)
   └── Opik (optional), JSON logs to stdout
```

- **Server = workflows**: code decides the path; the LLM performs bounded steps with structured outputs.
- **Client = agent**: the host LLM decides which tool to call, guided by prompts/instructions/skill.
- **Modes**: local (Docker Compose, no auth, `user_id="local"`, exposed only on 127.0.0.1 — the container binds 0.0.0.0 and compose publishes `127.0.0.1:8000:8000` —, FastMCP Host/Origin guard with `host_origin_protection=True`) and remote (Azure, Descope auth fail-closed, per-user limits, `stateless_http=True` passed to `run()`/`http_app()`). Same code; behaviour selected by settings.
- **No server-side state in memory between requests**: runs, claims, drafts, leases and pending changes live in Postgres. Nothing depends on the MCP session id.
- **Guards are server-side**: ownership, approval, confirmation phrases, profile completeness and limits are enforced in code; MCP annotations and prompts are hints only.

---

## 6. Configuration

Settings via pydantic-settings; secrets as `SecretStr`. The real `.env` is outside the repo; `ENV_FILE_PATH` points to it. Server-side constants (thresholds, TTLs) live in `config/constants.py`.

| Variable | Purpose | Default |
|---|---|---|
| `ENV_FILE_PATH` | Path to the real `.env` | — |
| `APP_ENV` | `local` / `production` | `local` |
| `DATABASE_URL` | Postgres URL (`postgresql+psycopg://…`) | compose service |
| `TEST_DATABASE_URL` | Test database; its name must end in `_test` | compose `laburo_test` |
| `LLM_BASE_MODEL` | Model for every task unless a task overrides it | `gpt-6-luna` **[verify]** |
| `LLM_CLIENT_MODEL` | Terminal client ReAct loop | empty → base model |
| `LLM_JUDGE_MODEL` | Eval judge | empty → base model (a larger model such as Sol is a candidate, decided by experiment) |
| `OPENAI_API_KEY` | OpenAI key | — |
| `SERPAPI_API_KEY` | Google Jobs via SerpApi (optional; source skipped if empty) | empty |
| `SERPAPI_MONTHLY_CAP` | Hard stop for SerpApi searches per calendar month (searches, replans and fixture recording) | 200 |
| `OPIK_API_KEY`, `OPIK_PROJECT`, `OPIK_WORKSPACE` | Observability (optional) | empty |
| `OBS_CAPTURE_PII` | Capture profile/draft content in traces | `false` |
| `DEMO_MODE` | Sources replay fixtures (no SerpApi key needed) | `false` (set `true` in the local `.env` until phase 4) |
| `SERVER_HOST`, `SERVER_PORT` | Bind address and port of the HTTP server (the container sets `0.0.0.0`) | `127.0.0.1`, 8000 |
| `UPLOAD_SIGNING_SECRET` | HMAC for signed upload links and user hashes | — |
| `PUBLIC_BASE_URL` | Base URL for upload links | `http://localhost:8000` |
| `DESCOPE_*` | Auth (remote only) | empty |
| `MAX_NEW_JOBS_PER_SEARCH` | Safety limit per search: a search queues every job that passes the filters, this only stops a runaway one | 300 |
| `SCREEN_ROUND_SECONDS` | How long one `screen_batch` round keeps taking jobs: the user waits ~30 s for the first results | 20 |
| `SCREEN_MAX_JOBS_PER_CALL` | Safety limit on the jobs one round may take | 300 |
| `CLAIM_STALE_SECONDS` | `processing` claims older than this are reset to `pending`; must exceed the longest `screen_batch` call | 300 (set from measurements) |
| `DRAFT_LEASE_SECONDS` | Lease duration of a draft execution | 300 (set from measurements) |
| `SLOW_TOOL_WARNING_SECONDS` | Log warning threshold (set from measurements) | 30 |
| `LLM_CONCURRENCY` | Parallel LLM calls | 4 |
| `EXTRACTION_BATCH_SIZE` / `LINKING_CHUNK_SIZE` | Set by experiments | 1 / 15 |
| `JOB_MAX_AGE_DAYS` | Freshness filter (default for new profiles) | 60 |
| `DEFAULT_MAX_COMMUTE_KM` | Default commute distance for new profiles | 30 |
| `DAILY_COST_CEILING_USD`, per-user limits | Cost control (remote) | see §17 |

---

## 7. LLM layer

All calls go through `llm.run(task, variable_input, ...)`. The registry declares, per task: prompt (stable prefix), few-shot examples (stable prefix), output schema, optional model override (default `LLM_BASE_MODEL`), reasoning effort, temperature (only if the model supports it **[verify]**), max output tokens. The factory builds the prompt (stable prefix first), creates a `ChatOpenAI` client on the Responses API (`use_responses_api=True` **[verify]**), computes the **automatic version hash** (prompt + examples + schema + model + model parameters), attaches Opik tags, records usage (including `cached_tokens`) in the usage module, and uses a `prompt_cache_key` per task.

| Task | Input (variable part) | Output | Notes |
|---|---|---|---|
| `profile_build` | CV text | Evidence list + inferred fields (incl. language levels with source) | Once per CV |
| `search_plan` | Profile summary, decisions summary, past run stats | `SearchPlan` (queries per source, excluded terms, notes) | Validated by code; ≤ 1 replan; not cached (stored in the run) |
| `job_extraction` | One job | `JobFacts` (below) | Cached per job; 2 few-shots |
| `requirement_split` | One job's requirements | Per requirement: `combinator` ∈ `all` / `any` and `atoms[]` (one thing each; qualifiers, purposes and years dropped; "A or B" → `any`) | Cached per job; one-line invented examples |
| `requirement_linking` | Chunk of unique pending **atoms** + enumerated evidence (names and quotes only: no dates, years or strength) | Per atom: list of `{evidence_id, relation}` with relation ∈ `direct` / `related`; empty list if none | **No level**; cached per evidence set; one-line invented examples |
| `profile_update_parse` | User's change in natural language | Structured profile diff | Preview only (stored in `profile_changes`); applied on confirmation |
| `job_qa` | Question + job text | Status + answer + verbatim quote(s) | Only when extracted facts cannot answer |
| `draft_write` | Job facts, linked evidence, guidelines, user style | Cover letter + CV bullets + screening answers | |
| `draft_review` | Draft + facts + guidelines | List of `Review` items | Highest reasoning effort |
| `draft_edit` | Draft + reviews | Revised draft | |
| `judge_*` | Eval items | Binary criteria with one-line reasons | Eval only, `LLM_JUDGE_MODEL` |

**`JobFacts`** (quotes verbatim in the original language; normalized values in English). Phase 2 ships the subset below; the rest arrives with its phase. Strict structured output needs every field, so "nothing found" is `[]` or `""`.
- `is_job_posting`, `language` (ISO 639-1), `work_modality` ∈ `remote` / `hybrid` / `onsite` / `unknown`.
- `apply_email`: `""` unless the posting states one; code keeps it only if it is a valid address that appears verbatim in the job text.
- `restrictions[]` (shape validated in spike 1.5): each with `kind` ∈ `location` / `citizenship` / `work_authorization` / `payroll` / `timezone` / `visa` / `modality`, `evidence_kind` ∈ `explicit` / `inferred` / `contradictory`, `quotes[]`, `places[]` (as written), `place_scope` ∈ `countries` / `region` / `worldwide` / `not_applicable`. A contradiction is one restriction with `evidence_kind = contradictory` and both quotes. Code verifies the quotes: an unverifiable quote is dropped, and a restriction left without enough verified quotes (1 for `explicit`, 2 for `contradictory`) is downgraded to `inferred`, so it can only make a job `doubtful`.
- `office_locations[]`: `"City, Country"` strings as written; empty if none. Phase 4 normalizes them to `{city, region, country_code}` for hybrid/on-site.
- Title, apply link and salary come from the source adapter in phase 2. Later phases add to the task: `requirements[]` (each with `type` (skill, experience, language, education, credential, soft, condition), `required` ∈ `required` / `nice_to_have` / `unspecified`, `min_years`, normalized text, language + CEFR level when type is language, quote, plus `combinator` and `atoms[]` filled by the `requirement_split` task), seniority words, and `flags` (agency signals, laundry-list signals).

Rules: Responses API (function calling with reasoning) **[verify]**; strict structured outputs (all fields required, nullable where optional) **[verify]**; the client ReAct loop uses `LLM_CLIENT_MODEL` through the same factory.

---

## 8. Profile model

Required for `is_complete`: **country, work authorizations, accepted modalities, target roles, CV uploaded** (plus a confirmed home location and max commute distance when hybrid or on-site is accepted). Everything else optional, inferred from the CV or asked when first needed.

| Section | Fields | Used for |
|---|---|---|
| Contact | name, email, LinkedIn, GitHub, portfolio | Drafts only |
| Hard constraints | country; citizenships (ISO list); work authorizations (countries/regions, e.g. `AR`, `EU`); security clearance (bool); visa sponsorship needed; accepted modalities (`remote`, `hybrid`, `onsite`); home location (geonameid, name, region, country, lat, lon, `source` = `exact` / `nearest_town`); `max_commute_km`; `extra_accepted_cities`; max office days per week; timezone (derived, editable); working-hours window; accepted contract types (`employee_local`, `contractor`, `eor`) with preference order; accepted payment currencies | Eligibility (filter) |
| Soft preferences | target roles, seniority, preferred stack, avoided stack, company types, min salary (amount, currency, period), full/part time, notice period | Ranking, drafts |
| Exclusions | companies, keywords, agencies flag, max job age | Prefilter |
| Evidence | items with id + label (E1…), kind (experience/skill/project/education/certification/language/other), normalized name, years (computed from dates), dates, quote, strength (`detailed` = used in a job bullet, dated by the jobs that use it / `mention` = only listed / `weak` = the CV itself qualifies it as basic or vague: "basic", "coursework", "familiar with"), source (`cv` / `user`), content hash, active flag; language items carry language, CEFR level and level source (`certificate` / `self_assessed` / `user_confirmed`) | Matching, drafts |
| Writing style | tone (`formal`/`neutral`/`casual`), length (`short`/`standard`), phrases to avoid, signature, notes (≤ 500 chars) | Drafts |
| Meta | `schema_version`, `profile_version`, `is_complete` | |

- **Evidence ID**: a short, stable label (E1, E2…) for each evidence item. The LLM answers with IDs only; code looks up years, quotes and strength by ID and rejects unknown IDs.
- **Evidence from the user** (`source=user`) captures their own arguments ("I master Python although I have used it for 2 years: built X and Y"). It counts as evidence and may be used in drafts as the user's claim, never turned into false verifiable facts.
- **Languages**: certificates are mapped to CEFR with a table in `config/data/levels.py` (e.g. Cambridge B2 First → B2, C1 with grade A; C1 Advanced → C1; C2 Proficiency → C2; TOEFL/IELTS score bands; DELE, DELF/DALF, Goethe, CELI/CILS, CELPE-Bras). Free-text levels ("advanced", "fluent", "native") are estimated by the LLM and marked `self_assessed`. `setup_profile` shows each language level for confirmation.
- **Known vs unknown**: optional constraint fields distinguish "never asked" (`None` → unknown) from a confirmed value, including a confirmed empty one (e.g. `citizenships = []`). Unknown values never produce `not_eligible` (§11.3).
- **Home location**: resolved once in `setup_profile` against `geo_places` and shown for confirmation ("Quilmes, Buenos Aires, AR"). If the city is not in the dataset or is ambiguous, the user names the nearest town in the dataset (`source = nearest_town`; distances are approximate).
- **Pending changes** are not part of the profile: `update_profile` previews live in `profile_changes` (§9).

---

## 9. Data model (PostgreSQL)

UUID primary keys exposed to the LLM; every private table has `user_id NOT NULL` with `ON DELETE CASCADE` from `users`. Shared tables (`jobs` from sources, `job_extractions`, `geo_places`) hold no personal data; jobs pasted with `analyze_posting` are private (`owner_user_id`). Job identity rules (canonical IDs, staleness) are in `CLAUDE.md`.

| Table | Key columns | Notes |
|---|---|---|
| `users` | id, external_id (auth sub), created_at | Seeded `local` user |
| `profiles` | user_id (1:1), constraints JSONB, preferences JSONB, exclusions JSONB, writing_style JSONB, profile_version, schema_version, is_complete | JSONB validated by Pydantic; every write is `UPDATE … WHERE profile_version = :expected` |
| `profile_changes` | id (= `change_id`), user_id, base_profile_version, diff JSONB, status (`pending`/`applied`/`superseded`/`stale`), created_at, expires_at | A new preview marks the previous pending one `superseded`. Applying runs `UPDATE profiles … WHERE profile_version = :base_profile_version`; 0 rows → `stale` → `PROFILE_CHANGED` |
| `evidence` | id, user_id, label, kind, name, normalized_name, years, `periods` (JSONB list of [start, end] intervals; years are their union), quote, strength, source, content_hash, language/cefr/level_source (languages), active, cv_file_id | New CV deactivates old CV evidence |
| `cv_files` | id, user_id, content BYTEA, sha256, page_count, extracted_text, uploaded_at, active | ≤ 5 MB, PDF only |
| `jobs` | id, source (`google_jobs`/`getonbrd`/`pasted`), external_id, owner_user_id (NULL = from a source, shared; set = pasted, private), url, apply_url, company, company_normalized, company_domain, title, location_text, modality (`remote`/`hybrid`/`onsite`/`unknown`, as the source declares it; Get on Board `remote_local` → `remote`), residence_text (who may apply to a remote job as the source declares it: `anywhere` for Get on Board `fully_remote`, the expanded `location_tenants` countries for `remote_local`, else empty), raw_text, content_hash, language, posted_at, first_seen_at, last_seen_at, closed_at, fingerprint, canonical_job_id | UNIQUE (source, external_id) for shared jobs; UNIQUE (owner_user_id, content_hash) for pasted jobs; fingerprint for cross-portal dedupe (shared jobs only); `canonical_job_id` NULL on canonical rows, duplicates point directly to a canonical |
| `job_extractions` | job_id, version_hash, content_hash, status (`ok`/`failed`), facts JSONB, chars_read, created_at | Cache key (job_id, version_hash, content_hash); a hit also needs `chars_read` = length of the capped text sent today, so a changed size cap re-extracts only the postings it cut |
| `geo_places` | geonameid, name, names TEXT[] (normalized name + alternate names), country_code, admin1_code, admin1_name, lat, lon, population | Shared reference data from the pinned GeoNames snapshot; GIN index on `names`, index on `country_code` |
| `search_runs` | id, user_id, kind (`search`/`single`), plan JSONB, status, created_at, expires_at, `funnel` JSONB with counters (in, after_prefilter, over_cap, extracted, extraction cache hits, linking cache hits, llm calls, tokens, cached tokens, cost) | `single` runs: `analyze_posting` and re-screens of one job |
| `run_jobs` | run_id, job_id, user_id, position (run-scoped display number), status (`pending`/`processing`/`done`/`failed`), attempts, claimed_at, last_error, prefilter_reason, eligibility, eligibility_reason, eligibility_quotes, recruiter_questions JSONB, profile_questions JSONB, distance_km, fit_band, gaps JSONB, flags JSONB, screening_hash, screened_at | PK (run_id, job_id); composite FK (run_id, user_id) → `search_runs` keeps `user_id` consistent; index (user_id, job_id, screened_at); claimed with `FOR UPDATE SKIP LOCKED` |
| `atom_links` | user_id, atom_key, evidence_set_hash, version_hash, links JSONB (`evidence_id`, `relation`, `evidence_content_hash`), level, created_at | Linking cache (§11.4, §14) |
| `decisions` | user_id, job_id (canonical), status (`saved`/`discarded`/`applied`/`interviewing`/`rejected`/`offer`), reason, reason_tags, eligibility_wrong, updated_at | One row per (user, job); idempotent upsert |
| `drafts` | id, user_id, job_id (canonical), version, status (`running`/`done`/`failed`), lease_until, attempt, content JSONB, reviews JSONB, created_at, updated_at | One row per (user, job): the row is the lease. Each generation increments `version` and runs on `thread_id = {draft_id}:{version}`; when it ends, the result is stored in `content` and the LangGraph thread is deleted |
| `usage_events` | user_id, kind (`tool_call`/`llm`/`serpapi`), task, units, cost_usd, cached_tokens, created_at | Quotas, SerpApi monthly cap, ceilings, cost display |

Runtime:
- Small psycopg 3 pool with `pool_pre_ping`; one session per concurrent task; a separate small psycopg pool for the LangGraph checkpointer (it needs autocommit).
- At container start, under one advisory lock: Alembic migrations; checkpointer `setup()` (its tables are excluded from Alembic autogenerate with `include_object`); the GeoNames load into `geo_places`, skipped when the snapshot's manifest hash is unchanged.
- Idempotent `cleanup()` at startup: expired runs, expired `profile_changes`, old CVs per retention, stale `processing` claims reset to `pending`.
- All timestamps come from `core.clock.now()` and reach SQL as `:now`.
- Neon note: the pooled endpoint (PgBouncer transaction mode) needs psycopg prepared statements disabled (`prepare_threshold=None`); prefer the direct endpoint.

---

## 10. Sources

| Source | Access | Parameters | Notes |
|---|---|---|---|
| Google Jobs (SerpApi) | API key, 250 searches/month and 50/hour on the free plan **[verify]**; hard cap in code (`SERPAPI_MONTHLY_CAP`) | queries (from the plan); location and language (from the profile); recency | Aggregates Bumeran, Computrabajo, LinkedIn, etc.; full descriptions; prefer the original portal link |

**Google Jobs via SerpApi, read in the docs on 2026-11-27 (no searches spent; confirm with real samples at the start of phase 4):** up to 10 results per request and every successful request is one search, so the monthly cap buys at most ~2,000 results for all users together: SerpApi complements Get on Board, it can never cover "every job". Pagination is `next_page_token` (`start` is discontinued). `ltype` (work from home) and `chips` are deprecated. Results carry `location` as text ("Austin, TX"), `detected_extensions` (`posted_at` as relative text, `salary`, `schedule_type`), `description`, `job_highlights`, `apply_options`, `via` and `job_id`, but **no remote/hybrid/on-site field**. Consequences: the `office_abroad` prefilter cannot act on these jobs (their modality is `unknown`), so the office-country rule of §11.3 must also run at screening, from the extracted `work_modality` and `office_locations` plus the `location` text; the query itself should target the user's country (`location`/`gl`) so on-site results are mostly local; the same job arrives from several boards, so cross-portal dedupe is required. Cached searches (1 h) are free.
| Get on Board | Public API v0, no key: `GET /api/v0/categories/{category}/jobs?per_page=120&page=N&expand=["company"]` (and `/api/v0/search/jobs?query=` for keywords, phase 4) | categories (from the plan) in phase 2; keywords from phase 4; remote/seniority filtered on our side | Main LATAM tech source. `per_page` is capped at 120 (a category is ~290 jobs: 3 requests). Structured location fields `countries` and `remote_modality` (`fully_remote` / `remote_local` / `hybrid` / `no_remote`) are what hybrid/on-site needs in phase 4. See the terms below |
| Pasted posting | `analyze_posting(text)` | — | See §11.6; private to the user |

**Get on Board terms** (help article "How can I use Get on Board's public API to show jobs on my site?", binding text in Section 7.1 of its Terms; read in phase 2): free and no key, including inside an AI product, as long as: (1) "Get on Board" is shown as the source with a link to each job's `public_url`; (2) applicants apply on its page and we never collect applications, CVs or contact details for these jobs (the server never sends applications anyway); (3) job data is shown as the API returns it and our analysis is kept apart and labelled as ours; (4) jobs are refreshed at least every 24 h and removed within 24 h of the API no longer returning them; (5) stay under the rate limit (20 requests per 5 s per IP at the time of writing, not contractual; slow down on 429); (6) no charging job seekers, no selling the data, no model training, no profiling professionals. A personal assistant that fetches jobs at one user's request, only for that user, and builds no listing of its own is explicitly not affected: every search fetches live, `jobs` is a cache. Apply route for these jobs is `public_url`; none of the 15 spike postings carried an email. Phase 4 must mark jobs the API stops returning as closed; phase 8 must keep results per user's own fetch.

`DEMO_MODE` replays one recorded page (`fixtures/sources/getonbrd/page-1.json`, 30 jobs, recorded with `scripts/record_fixtures.py`) and moves its dates forward so the newest job reads as published now.

All adapters share one protocol, normalize to the same `Job` model (including the declared modality and countries when the source has them, as structured fields, never as text for the model), report per-source errors without failing the search, and replay fixtures in `DEMO_MODE`. There are no per-user source settings: parameters come from the profile and the plan, and a source is enabled when its key (if any) is configured.

**Blocked sites** (`config/data/known_sites.py`, the single list): LinkedIn, Bumeran, ZonaJobs, Computrabajo, Indeed. The server never fetches any posting URL; the list tells hosts where to ask the user to paste the text and ranks apply links (company/ATS first, aggregators last).

**GeoNames** (offline): pinned snapshot of `cities500` (~185k places) and `admin1CodesASCII.txt`, committed under `data/geonames/` with a `MANIFEST` (source URL, download date, SHA-256, CC BY 4.0); refreshed only on purpose with `make update-geonames`, because GeoNames regenerates its dumps daily. Loaded into the shared `geo_places` table by an idempotent step at startup, under the migrations advisory lock, skipped when the manifest hash is unchanged. A unit test checks the files against the manifest; tests load a small subset. Matching: normalized name + alternate names, filtered by country code, then region, then population.
- User location: resolved once in `setup_profile` and confirmed by the user; stored in the profile as `home_location` (§8). If the city is not found, the user names the nearest town in the dataset.
- Office locations: resolved per job; not found or ambiguous → `doubtful`.

---

## 11. Pipelines

### 11.1 `search_jobs`
1. Require a complete profile (`PROFILE_REQUIRED` otherwise).
2. **Plan**: `search_plan` task (fallback: deterministic plan from roles × modalities). Code validates: allowed sources, max queries per source (SerpApi budget and `SERPAPI_MONTHLY_CAP`), no duplicates. The plan is stored in the run, not cached.
3. **Fetch** in parallel from enabled sources (hybrid/on-site queries use the user's home location).
4. **Normalize** to `Job`; upsert; compute `content_hash` and cross-portal `fingerprint` (normalized company + title + location).
5. **Deduplicate** within the run and against existing canonical jobs (shared jobs only); duplicates resolve to their canonical.
6. **New for the user**: keep only jobs with no decision and no judged `run_jobs` row for this user. A row still `pending` (or `processing` with an expired claim) is not judged: the new run **takes the job over** (its old row is deleted, so a job waits in one run only) and reports it as `carried_over`. Only jobs this search fetched again are taken over (a posting the source no longer returns is probably closed). Rows `done`, `failed`, or `processing` under a live claim count as seen.
7. **Prefilter** (deterministic, discards only when incompatible with the profile): exclusions, older than max age, closed, **`duplicate`** (same employer, title and place within the search: the newest posting is kept; without an employer name nothing is merged), **`residence_abroad`** (the source declares the job remote only for people in countries that are all known and not the user's, same prose guard), **`office_abroad`** (the source declares the job hybrid/on-site and every declared country is known and not the user's, and the prose names no place that may include the user's country; runs before the cap, no LLM), other role family (explicit blocklist in `config/data/role_families.py`, applied only when the title shares no keyword with the target roles or stack), and high-confidence restriction phrases from `config/data/locations.py` **only when the profile does not satisfy them** (e.g. "US only" is not discarded for a user with US work authorization). Each discard gets a `run_jobs` row (status `done`, `prefilter_reason`) and is visible as `filtered`.
8. **Order and safety limit**: every job that passed the filters is queued, ordered by title relevance (screening follows this order, so the most relevant are judged first). Only if more than `MAX_NEW_JOBS_PER_SEARCH` (a safety limit, 300) remain: order by title relevance (overlap with target roles and stack), then recency, and keep the cap; the rest are counted as `over_cap` (no row: they can enter a later search). Create `search_run` + `run_jobs` (status `pending`).
9. **Replan once** if the pool after prefilter is too small (threshold in constants); the replan counts against the SerpApi cap.
10. Return: `run_id`, counts per source, discard counts by reason, `over_cap`, a one-line plan summary ("Searched: … Excluded: …").

### 11.2 `screen_batch(run_id)`
Idempotent and safe under concurrency. One call is one **round bounded by time** (`SCREEN_ROUND_SECONDS`): `LLM_CONCURRENCY` workers each take the next job by relevance, judge it and save it at once, until the time is up; jobs still in flight at the deadline go back to `pending` without counting an attempt (their extraction, if finished, is cached). Every round returns the best jobs judged so far and `remaining`.
1. **Claim** the next `pending` job of the run (one per worker, in relevance order) with `SELECT … FOR UPDATE SKIP LOCKED`, set them to `processing`. A second concurrent call claims different jobs or none. `processing` rows older than `CLAIM_STALE_SECONDS` are reset to `pending` (crash recovery). If the call is cancelled (host timeout), its claims are released in a `finally`. Already `done` jobs are never reprocessed.
2. **Extraction** (`job_extraction`): cache lookup; the round's first job runs alone to warm the prompt cache, then the workers run in parallel; malformed output → one retry with the validation error. Content is sanitized (HTML, scripts, zero-width/control chars) and capped (~30k chars).
3. **Eligibility** (deterministic, §11.3).
4. **Matching** for `eligible` and `doubtful` jobs (§11.4).
5. **Scoring, flags, ordering**, **aggregated gaps** and **aggregated profile questions** across the run. Each row stores its `screening_hash`. Jobs move to `done`.
6. **Failures**: a failing job increments `attempts`; it returns to `pending` once (a worker of the same round retries it); after 2 failures it is `failed` and reported as "could not process" with a short reason. One failure never fails the call.
7. **Return**: every round returns the shortlist of the best jobs judged so far (≤ 10 cards), status `partial` while `remaining > 0` (the hint tells the host to show the results and continue only if the user asks) or `done`, with + discarded counts by reason + doubtful items with questions for the recruiter + profile questions + `common_gaps` + `failed` count + `next_step_hint`.

### 11.3 Eligibility (code)

**Definitions** (testable):
- **`not_eligible`**: at least one **explicit** restriction, not contradicted by another explicit statement, that the profile **known** values do not satisfy. The card shows the restriction and its quote.
- **`eligible`**: every explicit restriction is satisfied by known profile values **and** there is at least one explicit compatible location signal ("Remote — LATAM", "Argentina", an office within the commute distance) **and** there are no contradictions.
- **`doubtful`**: everything else — no location information, only inferred restrictions, contradictory explicit statements, ambiguous regions, unresolvable office location, borderline timezone overlap, or a restriction that depends on a profile field the user has not answered yet. The card shows the reason, the quotes, suggested questions for the recruiter and, when relevant, the profile question.

**Precedence**: inferred restrictions can only produce `doubtful`; contradictory explicit statements → `doubtful` with both quotes; unknown profile values → `doubtful` + a profile question, aggregated at the review stop ("3 jobs require US citizenship. Do you have it?"); the answer goes through `update_profile` and the re-screen is code only (0 LLM calls); rules never approve, they only compare.

**Declared evidence**: what the source states in its own fields (Get on Board's remote work policy: modality, office countries, who may apply) is explicit evidence apart from the text, cited on cards as "As listed on Get on Board: …". Open to the user (fully remote, or a residence list that includes their country): places in the text the code cannot read become notes, a country in the text that excludes the user makes the job `doubtful`, and other explicit requirements are still judged. Closed (residence or office in other countries only): `not_eligible`, or `doubtful` when the text says the job is open to the user.

**Checks** (each compares an extracted restriction with the profile):
- **Location / region**: places resolved with the table in `config/data/locations.py` (country names, region → countries, ambiguity flags). An explicit "Worldwide" / "Anywhere" / "Work from anywhere" counts as a compatible location signal **only when nothing else in the posting excludes the user's country** (another restriction is still judged on its own and can make the job `not_eligible` or `doubtful`); "Americas", "EMEA", "APAC" or a place the table does not know → `doubtful`.
- **Work authorization, citizenship, clearance**: payroll and citizenship phrases are mapped to requirements — "W2 only", "US SSN" → US work authorization ("1099 contractor" is only a badge: a contractor abroad signs a W-8BEN); "US citizens only" → US citizenship; "security clearance" → US citizenship + clearance — and compared with the profile.
- **Timezone / hours**: phrases ("US hours", "EST overlap", "core hours 9–1 ET") → UTC windows (table) compared with the user's working window; unknown window → profile question; DST borderline → `doubtful`.
- **Contract type and payment currency**: compared with accepted types/currencies (unknown → no effect on the verdict; shown as a badge).
- **Modality**: remote → location/authorization checks. Hybrid/on-site → each office in `office_locations` is resolved (LLM-normalized city/region/country → `geo_places`) and the job is accepted if any office is within `max_commute_km` of the user's home location or in `extra_accepted_cities`; office days ≤ the user's max (unknown max → profile question). An office whose **country** is known (the posting or the source's structured country) and is not the user's country → `not_eligible`, even when the city is unknown (when the source declares modality and country, the search prefilter already discarded it as `office_abroad`, see §11.1); with a known city the distance rule above applies. Unknown country, or an ambiguous or unresolvable city inside an acceptable country → `doubtful`. Distances from a `nearest_town` home location are marked approximate.
- Outputs always say: "Eligibility is an estimate based on the posting text, not legal advice; confirm with the employer."

### 11.4 Matching

The LLM **links**; code **decides**.

| Step | Type | What happens |
|---|---|---|
| Code-only types | Code | `language`: compare CEFR levels per language (equal or higher → `met`; lower → `partial` with gap size; absent → `missing`; self-assessed noted). `education`: ordinal scale; "or equivalent experience" counts as met with sufficient years. `soft` → `not_assessable` (hidden by default, never scored). `condition` → shown separately, never scored |
| Split | LLM (job level) | Each requirement of a job becomes `{combinator, atoms[]}` once, cached with the job; the same for every user. Linking only ever sees atoms |
| Key | Code | `atom_key` = normalized atom text + min_years (the requirement's); `requirement_key` = normalized requirement text + type + min_years identifies the requirement inside a job |
| Cache | Code | Exact lookup by `(user, atom_key, evidence_set_hash, version_hash)`. On a miss, the latest row for `(user, atom_key, version_hash)` is reused only if its stored level was `met` and every linked evidence item is unchanged (same content hash) and still active; everything else is re-linked |
| Linking | LLM | Remaining atoms, **deduplicated across the run**, chunked, in parallel: per atom, the evidence IDs with relation `direct` (the evidence is that thing under any name) or `related` (similar but different; only an argument hint), or none. The LLM never decides levels, compares years or judges whether a compound requirement is covered |
| Validation | Code | Evidence IDs must exist; unknown IDs are dropped and flagged |
| Level | Code | Per atom, then per requirement: rules below |
| Store | Code | Cache row with links, level and the content hash of each linked evidence item |

**Level rules** (code). Years are the union of the date intervals of the `direct` detailed evidence linked to the atom, so overlapping experiences are not counted twice.

| Links of the atom | Condition | Level |
|---|---|---|
| `direct`, detailed evidence | Years ≥ `min_years`, or no years requested | `met` |
| `direct`, detailed evidence | Years < `min_years` | `partial` with `gap_size` (`small` ≤ 50% short, else `large`) and an argument hint |
| `direct`, mention-only evidence | Requirement asks for years | `partial` ("mentioned without detail") |
| `direct`, mention-only evidence | No years requested | `met` |
| `direct`, only `weak` evidence | — | `partial` ("weak mention"), never `met` |
| Only `related` | — | `missing`; the related evidence is shown as the argument hint ("you have X; argue it for Y") |
| None | — | `missing` |

**Combining atoms** (code, per requirement): `all` → `met` only if every atom is `met`; `missing` if no atom has any coverage; otherwise `partial`. `any` → the best atom wins.

- **Fit band**: required requirements weigh more; any `missing` required requirement caps the band at Medium; `unspecified` weighs in between.
- **Seniority fit** (code): job seniority words + required years vs user seniority and years → under / fit / over.
- Each card: one-line pro/con, badges (payment currency, contract type, overlap, distance for hybrid/on-site, age, flags: agency, possible ghost job, reposted, laundry-list), best apply route (company/ATS link → `apply_email` → aggregator link).
- **Profile corrections**: new or edited evidence → new `evidence_set_hash` → only affected requirements re-linked (one batched call) → `update_profile` returns the fit delta for the latest search run ("job 2: Medium → High"). The computation fills the linking cache, so the later lazy re-screen of each job (staleness rule) costs no LLM calls.

**To validate and tune in phase 5** (open from spike 1.7; measure on the larger eval set with dev/test split, then decide):
- **Requirement qualifiers** ("advanced", "strong", "solid"): `requirement_split` also stores the qualifier per requirement; the level still comes only from the evidence, and the card shows the qualifier next to the evidence ("the posting asks for advanced Node.js; your CV shows 2.7 years detailed: confirm it or prepare to argue it"). Whether required + "advanced/expert" should lower the level to `partial` is decided with data, not now.
- **Implied relations** (`SQL` ← `PostgreSQL`, judged `related` in every run of spike 1.7): add one-line invented examples to `requirement_linking` ("SQL" ← "MySQL": `direct`), never a general "A implies B" rule (it would turn Next.js into Node.js backend experience). Re-validate on postings not used for tuning.
- Fix `LINKING_CHUNK_SIZE` with the experiment {1, 15, all} (spike 1.7 used 15 only), and measure the stability of `requirement_split` across calls.

### 11.5 `ask_posting(job_id, question)`
1. If the question maps to an extracted field (salary, modality, office, stack, contract, timezone, location, requirements, apply email), answer from stored facts with their stored quotes (0 LLM calls).
2. Else `job_qa` with the job text; every quote verified by exact match after normalization.
3. Response status: `answered` (with quotes), `not_mentioned`, `ambiguous` (quotes that leave it unclear), `contradictory` (conflicting quotes). No valid quote → `not_mentioned`.
4. Answers come from job facts, which do not depend on the user, so `ask_posting` never re-screens.

### 11.6 `analyze_posting(text, url="")`
Input contract:
- `text` empty → `INVALID_INPUT` ("Paste the posting text; the server does not fetch URLs.").
- `url` is optional and stored only as the reference link; **nothing is fetched**.

Flow:
1. Sanitize and cap the text (same rules as §11.2); compute its content hash.
2. Same user already pasted the same text → reuse that job.
3. Create a private job (`source = pasted`, `owner_user_id` = user); it never takes part in cross-user dedupe.
4. `is_job_posting` false → `NOT_A_JOB_POSTING`.
5. Same pipeline as screening in a `single` run; returns the card.

### 11.7 Draft workflow (`draft_application`)
Requires a saved decision for the job (`APPROVAL_REQUIRED` otherwise). If the job's latest `run_jobs` row is stale or missing, the job is re-screened first (`single` run). LangGraph functional API, Postgres checkpointer (psycopg 3), `RetryPolicy` per task, progress events. Every non-deterministic operation (LLM calls, clock reads) is inside a `@task`.

**Execution control** (lease):
- One `drafts` row per (user, job): the row is the lease. Before running, a conditional update (`status != 'running' OR lease_until < :now`) sets `status = running` and `lease_until = :now + DRAFT_LEASE_SECONDS`; a new generation or a feedback round also increments `version`.
- If a valid lease exists → return "The draft is being generated; try again in a few seconds" (no second execution).
- If a `running` draft has an expired lease (crash) → resume with `invoke(None)` on `thread_id = {draft_id}:{version}`; completed tasks are restored from the checkpoint, not recomputed.
- If the call is cancelled, the lease is expired in a `finally`; the status stays `running`, so the next call resumes from the checkpoint.
- On success the result is stored in `content` with `status=done`, the lease is released and the LangGraph thread is deleted; on repeated failure `status=failed` with the reason (thread deleted too).
- **Timeouts**: if the measured draft time (spike 1.3) does not fit under half the smallest host timeout, each call advances a bounded number of steps and returns `in_progress`; the host calls again and the run resumes from the checkpoint. FastMCP background tasks are not used.

**Steps:**
1. **Write**: cover letter (≤ 180 words), 5–7 tailored CV bullets, screening answers if the job lists questions; job language; rules from `src/prompts/application_guidelines.md` + user writing style (rules > user style > default style).
2. **Deterministic checks**: every claim maps to evidence IDs; length; language; banned phrases; never states unsupported authorizations, citizenship, years or salary.
3. **LLM review** → list of `Review` items (rule, problem, fix).
4. **Edit** with the reviews; loop until no major issues, max iterations, or no improvement.
5. **Safety net**: if the cap is reached with unsupported claims, remove those sentences.
6. Gaps are turned into arguments (user evidence, transferable experience), never hidden behind false facts.
7. Human feedback at the second stop becomes `Review(source="human")` with highest priority; one edit iteration.

---

## 12. MCP interface

### 12.1 Tools (12)
All parameters simple types with defaults; all results typed and compact with `next_step_hint`; stable error codes. Annotations are hints for hosts; every guard below is enforced in server code. `job_id` is always the canonical UUID from a card; a non-UUID value (e.g. a position) returns `JOB_NOT_FOUND` with "Pass the job_id from the card, not its position." The contract test "no `anyOf`" applies to input schemas.

| Tool | Inputs | Output (summary) | Annotations | Errors |
|---|---|---|---|---|
| `build_profile` | — | If no CV: signed upload link. Else: evidence summary, inferred fields, language levels to confirm, home location to confirm (hybrid/on-site), vague mentions (2–3), missing required fields | write, idempotent | `CV_UNREADABLE`, `CV_SCANNED` |
| `update_profile` | `change: str = ""`, `apply: bool = False`, `change_id: str = ""` | Preview (`change_id`, diff, base version) or applied result + fit delta for the latest search run | write | `NO_PENDING_CHANGE` (unknown, superseded or expired change), `PROFILE_CHANGED` (stale preview) |
| `search_jobs` | `max_new: int = 300` (capped by `MAX_NEW_JOBS_PER_SEARCH`; a search queues every job that passes the filters) | `run_id`, counts (incl. `already_seen`, `carried_over`), discard reasons, `over_cap`, plan summary | write, open-world | `PROFILE_REQUIRED`, per-source warnings (incl. SerpApi monthly cap reached) |
| `screen_batch` | `run_id: str` | One time-boxed round (~20 s). Every round: status `partial`/`done`, `remaining`, shortlist of the best judged so far, doubtful + recruiter questions, profile questions, discards by reason, `common_gaps`, `failed` | write, idempotent | `RUN_NOT_FOUND`, `RUN_EXPIRED` |
| `analyze_posting` | `text: str`, `url: str = ""` | One card | write | `INVALID_INPUT`, `NOT_A_JOB_POSTING` |
| `explain_match` | `job_id: str` | Full card: eligibility + quotes + disclaimer, requirements table with evidence, relation and "how to argue it", what the posting does not say, flags, best apply route, verdict | write (may re-screen a stale job) | `JOB_NOT_FOUND` |
| `ask_posting` | `job_id: str`, `question: str` | Status (`answered`/`not_mentioned`/`ambiguous`/`contradictory`) + answer + quotes | read-only | `JOB_NOT_FOUND` |
| `record_decision` | `job_id: str`, `status: Literal["saved","discarded","applied","interviewing","rejected","offer"]`, `reason: str = ""`, `eligibility_wrong: bool = False` | Saved decision; suggested exclusion if a pattern repeats | write, idempotent | `JOB_NOT_FOUND` |
| `list_jobs` | `status: Literal["saved","applied","interviewing","rejected","offer","discarded","filtered","all"] = "saved"`, `limit: int = 20`, `offset: int = 0` (phase 2 ships it read-only with `status: Literal["all","filtered"] = "all"` and pages of at most 50; the decision statuses and the `saved` default arrive with decisions in phase 6) | Jobs with status, days since update, reason, best apply route, closed flag, `stale` marker. `discarded` = discarded by the user; `filtered` = discarded by prefilters or eligibility, with the reason | read-only | |
| `draft_application` | `job_id: str`, `feedback: str = ""` | Draft (letter, bullets, screening answers) + 3-line summary of what was emphasized, or `in_progress` | write | `APPROVAL_REQUIRED`, `JOB_NOT_FOUND` |
| `get_workflow_instructions` | `workflow: Literal["setup_profile","review_jobs"]` | Step-by-step workflow text (same function as the MCP prompts) | read-only | |
| `delete_my_data` (phase 8) | `confirm_phrase: str` | Deletion summary (includes pasted jobs and LangGraph threads) | destructive | `CONFIRMATION_REQUIRED` |

### 12.2 Resources (4)
| URI | Content | MIME |
|---|---|---|
| `profile://me` | Profile including writing style (no contact data in remote mode unless requested) | application/json |
| `jobs://{job_id}` | Original job text + link + apply email + source (owner check for pasted jobs) | text/markdown |
| `pipeline://me` | Jobs by status | application/json |
| `system://status` | Version, models, Opik on/off, sources and last success, SerpApi monthly usage vs cap, cache hit rates (24 h), cost of the last search | application/json |

### 12.3 Prompts (2) and server instructions
Both prompts are built from shared fragments in `src/prompts/fragments.py`; `get_workflow_instructions` and the server `instructions` use the same functions.

**`setup_profile`**: call `build_profile` → (if needed) give the upload link and wait → show what was understood, language levels, home location (if hybrid/on-site), required fields missing, 2–3 vague mentions → **STOP** for corrections/confirmation → `update_profile` preview → **STOP** → apply (if `PROFILE_CHANGED`, preview again).

**`review_jobs`**: if no complete profile → run setup first → `search_jobs` → `screen_batch` while `remaining > 0` (intermediate calls only report progress) → present the shortlist with the header "Since your last search: N new eligible, M discarded" → **single STOP**: accept "ok" (keep recommendations), item edits ("3 yes, 2 no: no agencies"), evidence corrections, answers to aggregated gaps and profile questions → `record_decision` / `update_profile` → offer drafts → if requested: `draft_application` → **STOP** for approval or changes. Always pass the `job_id` from the cards, never positions. If the user shares a link: read it with your own web tools if available, except blocked sites, where you ask the user to paste the text; then call `analyze_posting`. Never call `draft_application` without a saved decision. Never mention internal terms (runs, versions, IDs) to the user.

**Server `instructions`**: 5–8 lines with purpose, typical order and the critical rules above. The terminal client injects them into its system prompt.

### 12.4 Skill
`.claude/skills/laburo-match/SKILL.md`: third-person description with trigger phrases (search jobs, review postings, check eligibility, set up profile, prepare an application); body: call `laburo-match:get_workflow_instructions` with the right workflow and follow it; stop where it says STOP; talk about jobs, fit and next actions only.

### 12.5 Custom HTTP routes
- `GET/POST /upload?token=…`: signed (HMAC), 15-minute link bound to the user; PDF validation; stores in `cv_files`; a second upload replaces the first.
- `GET /health` (liveness, version) and `GET /ready` (DB check).

---

## 13. Human-in-the-loop and UX

- One stop per batch; defaults; short replies; reasons optional.
- Gap aggregation: "LangGraph is missing in 6 of 10 eligible jobs. Do you have it? (yes + detail / no)".
- Profile-question aggregation: "3 jobs require US citizenship. Do you have it? (yes / no)".
- Doubtful items come with questions to ask the recruiter.
- Discards can be audited: `list_jobs(status="filtered")` shows each automatic discard with its reason; `discarded` lists the user's own discards.
- Users can report wrong eligibility verdicts (`eligibility_wrong=True`), stored as feedback and as eval candidates.
- Tone: describe and suggest, never lecture. Example: "You have 2 of the 5 years requested, but you built X; present it like this…".
- Eligibility always carries the disclaimer: estimate from the posting text, not legal advice.
- Best apply route first: company/ATS link, then apply email, then aggregator.
- All server messages are in English; the host presents them in the user's language.

---

## 14. Caching summary

| Cache | Key | Invalidation |
|---|---|---|
| Job extraction | job_id + version_hash + content_hash | Prompt/examples/schema/model/params change, or job content changes |
| Atom links | user + atom_key + evidence_set_hash + version_hash | Evidence change → new evidence_set_hash; a previous result is reused only if its level was `met` and all linked evidence is unchanged and active, the rest re-linked; model/prompt change → new version_hash |
| Provider prompt caching | Stable prefix per task (+ `prompt_cache_key`) | Automatic (≥ 1,024 tokens on OpenAI) **[verify]** |
| Eval LLM cache | task + version_hash + model + messages + params | Eval runner only; `--no-cache` for design experiments |

`version_hash` = hash of prompt + examples + schema + model + model parameters, computed automatically by the LLM factory. Search plans are not cached (one cheap call per search; stored in `search_runs`).

---

## 15. Observability

- Opik projects per environment (`laburo-match-dev`, `-eval`, `-prod`); client traces in their own project to separate orchestration cost from server cost.
- Thread = `run_id` (screening) or `draft_id` (drafts); the MCP session id is optional metadata only. Trace = tool call; spans = handler steps + LLM calls (LLM spans only from the LangChain tracer via `llm_callbacks(task)`; no duplicates).
- Metadata: task, model, reasoning effort, version hash, cache hit/miss, user HMAC, profile version, run id, batch/chunk sizes.
- Quality metrics: validation retries, citation verification failures, unsupported claims removed by the draft safety net, unknown evidence IDs dropped, contradictions detected, `apply_email` values rejected by verification.
- Feedback scores: user saved a job (1/0); user corrected a requirement; user reported a wrong eligibility verdict.
- PII off by default; jobs from sources (public) captured fully; pasted jobs follow `OBS_CAPTURE_PII`.
- JSON logs to stdout with correlation id and Opik trace id; warning when a tool exceeds `SLOW_TOOL_WARNING_SECONDS`.
- Day-1 check: LangChain spans nest correctly inside `asyncio.gather`.
- README figures: cost per search (first vs repeated) and per job, % of eligibility verdicts without LLM, % of requirements resolved by code or cache, % cached prompt tokens, eligibility distribution and top discard reasons, hallucination guardrail rates, experiment tables, p50/p95 latency per tool.

---

## 16. Security

Prioritized checklist (P0 before any deploy):
- P0: secrets outside the repo, `SecretStr`, `.dockerignore`, gitleaks (pre-commit + CI), GitHub secret scanning + push protection.
- P0: `uv sync --frozen`; uv constraint excluding the compromised LiteLLM versions (1.82.7, 1.82.8, 1.107.0) as defense in depth — current Opik already excludes them in its own requirements; verify the resolved version in `uv.lock`; Actions pinned by SHA; base image by digest.
- P0: structured outputs, delimiters for untrusted content, eligibility in code, exact-match verification of quotes and `apply_email`, static tool descriptions.
- P0: all guards (ownership, approval, confirmations, limits, profile completeness) enforced server-side, never via annotations or prompts.
- P0: no server-side URL fetching (no SSRF surface); content sanitization and length cap for pasted text and source data.
- P0: PDF limits (5 MB, 10 pages, parse in a subprocess with a timeout so it can be killed, magic bytes); no extraction of national IDs, date of birth or photos into the profile.
- P0: `user_id` from auth context, UUIDs, ownership helper (incl. private pasted jobs), tenant-isolation test with two users.
- P0: Descope fail-closed in production; local exposure only on 127.0.0.1 + FastMCP Host/Origin guard (`host_origin_protection=True`, DNS rebinding) **[verify in 3.x]**.
- P0: separate test database with a name guard; scrubbed fixtures (no third-party contact data in the public repo).
- P0 (remote): cost-aware per-user limits and global ceiling; SerpApi monthly cap; no PII in logs/traces; `delete_my_data` cascade (incl. pasted jobs and LangGraph threads); DB TLS + firewall; HTTPS ingress.
- P1: OIDC CD, per-environment keys and provider budget alerts, Dependabot (manual review) + pip-audit, non-root container, masked errors, 3–5 prompt-injection eval cases, privacy section and disclaimer in the README (assists, user decides, never auto-applies; eligibility is not legal advice; CV text is sent to the configured LLM provider).
- P2 (optional, phase 8): SBOM and image scanning, with the Action pinned by SHA.

---

## 17. Cost control

- One usage module with a price table per model: per-user quotas (remote), global daily ceiling ("service paused" when exceeded), SerpApi monthly cap (`SERPAPI_MONTHLY_CAP`), eval budget ($0.50 per run by default, `--budget` overrides), cost per search shown in `system://status`.
- Defaults (remote): searches/day, drafts/day, `ask_posting`/day per user — set in constants.
- Provider-side spend limits and alerts on OpenAI, SerpApi and Azure.

---

## 18. Evaluation

Evaluation starts in phase 1 (idea validation with 15 real postings, contact data scrubbed) and grows every phase. Every dataset is split into **dev** (~2/3, used to tune prompts and rules) and **test** (~1/3, held out, run only at milestones). With 20–40 items per dataset there is no separate validation split; this is documented in the README.

| Eval | Data | Metrics |
|---|---|---|
| Eligibility | ~30 real postings labelled eligible/not/doubtful + ~10 synthetic variants with hidden restrictions + inferred-only and contradictory cases + profiles with and without US authorization + profiles with unknown fields + tricky regions/timezones/payroll + hybrid/on-site distance cases in several countries (incl. multi-office postings) + 3–5 prompt-injection postings | Precision/recall per class; contradiction detection; rules-only vs rules+LLM vs plain-LLM baseline; cost |
| Extraction quality | Same postings, field-level labels (restrictions, evidence_kind, office locations, apply email, requirements) | Per-field accuracy; cost per job |
| Prefilter | Titles with synonyms of target roles and titles from other role families | 0 false discards; discard rate on noise |
| Profile independence | Same postings with 2 profiles (e.g. AR, AR+EU) | Verdict changes match expectations |
| Language consistency | ~5 postings translated ES↔EN | Same extraction and verdict |
| Matching | ~25 postings × requirements labelled with expected links and levels for the sample profile | Link accuracy (evidence + relation), level accuracy per class, **false-`met` rate** |
| Language levels | Certificates and free-text levels on both sides | Correct CEFR mapping and comparison |
| Seniority fit | ~10 labelled cases | Accuracy |
| `ask_posting` | Questions answerable, not mentioned, ambiguous and contradictory | Status accuracy, quote verification |
| `analyze_posting` | ~10 pasted texts (plain, structured, multi-office, not a posting) + input-contract cases | Correct outcome |
| Drafts | ~20–30 drafts | Binary rubric: `grounded`, `addresses_location_terms`, `covers_top_requirements`, `turns_gaps_into_arguments`, `job_language` (code), `within_length` (code), `no_cliches`, `follows_user_style` |
| Explanations | Sample of `explain_match` outputs | Binary: names every missing required requirement, every `met` cites evidence, disclaimer present |

Design experiments (Opik experiments, dev split): extraction batch size {1, 5, 25}; linking chunk size {1, 15, all}; few-shots on/off in extraction; base model alternatives; per-task model overrides (e.g. drafts); judge agreement with hand labels for the base model vs a larger candidate (e.g. Sol). Judge: `LLM_JUDGE_MODEL` (base model by default), 1–2 pass/fail examples per criterion; known limitation documented when judge and base share a model family.

---

## 19. Testing strategy

| Layer | Covers | When |
|---|---|---|
| Unit | Eligibility definitions and precedence (incl. unknown vs confirmed-empty profile values), region/timezone/payroll tables, role-family prefilter and cap ordering, GeoNames matching and distance, manifest check, level rules (incl. union of year intervals), CEFR mapping, scoring, dedupe and canonical resolution, quote and `apply_email` verification, draft checks, prompt assembly order, version hash (incl. model), `analyze_posting` input contract, fixture PII check | Every PR |
| Integration | Queries, migrations up/down/up, checkpointer `setup()` alongside Alembic, GeoNames load idempotency, cache keys and invalidation (edited/removed/added evidence), idempotency, `screen_batch` claims under concurrency, stale-claim recovery, cancellation releasing claims, `profile_changes` (superseded and stale previews), draft lease (no duplicate execution, resume after expired lease, thread deletion), staleness re-screen, private pasted jobs, tenant isolation | Every PR (real Postgres service, `laburo_test`) |
| Contract | Tool/prompt/resource names, descriptions, input schemas without `anyOf`, annotations, error shapes, server-side guards | Every PR (in-memory client) |
| E2E with fakes | search → screen → explain → decision → draft; cache hit on 2nd run; one source down; one job failing twice; draft loop always failing stops at the cap | Every PR |
| Client smoke | Client starts, lists tools, one scripted ReAct turn | Every PR |
| Evals | §18 | Manual (`workflow_dispatch` / `make eval`) |
| Live source check | Adapters parse real responses | Manual (`make record-fixtures`), ≤ 3 SerpApi calls |

Fakes: `FakeLLM` (scripted per task + schema, fails on unscripted calls, records calls), respx fixtures, frozen clock (`:now` passed to SQL), `OPIK_TRACK_DISABLE=true`, `tests/factories.py`. Database: separate `laburo_test` (the suite aborts on any other name); transactional fixture by default, committed + `TRUNCATE` fixture for concurrency, claim and lease tests. Detailed rules: `.claude/rules/testing.md`.

---

## 20. CI/CD and deployment

- **CI** (every PR): ruff, pyright, gitleaks, pip-audit, unit/contract/integration/e2e tests with a Postgres service (same major as Azure), on Python 3.14 (from `.python-version`). No secrets.
- **CD** (push to `main`, after CI): build image → push to GHCR (tag = commit SHA) → deploy to Azure Container Apps with `azure/container-apps-deploy-action` and OIDC → at container start, under one advisory lock: migrations, checkpointer setup, GeoNames load → `/health` smoke test.
- **Azure**: Container Apps (scale to zero; HTTPS ingress; secrets as Container Apps secrets; `stateless_http=True`; cold start measured at 23–26 s in spike 1.8, so a request that wakes the app can stack ~25 s on a tool call: decide in phase 8 between `min-replicas 1` during demos and evaluation windows, or a smaller image); managed Postgres (Azure Flexible Server if credits allow, else Neon direct endpoint) with TLS and firewall; budget alert. Document in `docs/azure-deployment.md`.

---

## 21. Phases

Each phase starts by writing `specs/phase-N-<name>.md` in plan mode (goal, tasks, definition of done; spike phases also write numeric go/no-go thresholds and a plan B per spike before running them) and ends with a PR and 3–5 learning-log bullets (private). Evaluation grows in every phase from phase 1. Hours are design estimates; with explanations and verification at every step, expect 1.5–2× in practice.

| Phase | Content | Exit criteria | ~Hours |
|---|---|---|---|
| 0. Setup | WSL2, tools, accounts, repo, `uv init --python 3.14.0 .` then `.python-version` = `3.14`, `.gitignore`/`.gitattributes`, `.env.sample`, env outside repo, CLAUDE files, specs | Clean repo, hooks working, keys outside the repo | 3 |
| 1. Risk spikes (`spikes/`) | 1.1 deps on 3.14 (incl. FastMCP 3.x, psycopg 3) + LiteLLM version resolved in `uv.lock` + FastMCP 3.x still patched · 1.2 Docker + Postgres (major supported by Azure Flexible Server) + Alembic + checkpointer `setup()` alongside Alembic + `laburo_test` · 1.3 FastMCP HTTP tool visible in Cursor, Claude Code, Claude Desktop (from Windows) and Inspector + measure each host's tool timeout + time a draft-like LLM loop · 1.4 LLM: `ChatOpenAI` on the Responses API, strict structured output, tool calling with reasoning, accepted params, `cached_tokens`, Opik nesting · **1.5 idea validation: 15 real postings (scrubbed), hand labels vs extraction (explicit/inferred/contradictory)** · 1.6 pypdf in a subprocess with timeout on a real and the sample CV + evidence and language-level quality · 1.7 linking + level rules on 5 jobs · 1.8 Azure hello-world MCP with `stateless_http=True`: progress notifications and session id behaviour | Go/no-go review against thresholds written before running the spikes; fixtures (scrubbed) and first dev/test labels saved; design adjusted if needed | 16 |
| 2. Vertical slice | Structure, settings, `LLM_TASKS`, core tables, Get on Board only, seeded profile, `search_jobs` → `screen_batch` (basic, with claims) → shortlist in the client, FakeLLM tests, test DB fixtures, CI, eligibility eval harness (dev/test) | End-to-end flow works and is tested | 15 |
| 3. Profile | `/upload`, `build_profile`, `update_profile` two-step with `profile_changes`, `setup_profile`, CEFR mapping, writing style, known vs unknown fields, `is_complete` | Onboarding works end to end | 9 |
| 4. Search & eligibility | SerpApi (with monthly cap), cross-portal dedupe + canonical resolution, profile-aware prefilters (role families, cap ordering), location/timezone/payroll tables, eligibility definitions and precedence, profile questions, planner + replan, freshness, agency/ghost flags. **Last, decoupled block**: hybrid/on-site (GeoNames snapshot in `geo_places`, home location confirmation, `office_locations`, distance) | Full search with audited discards; eligibility eval on dev split | 14 |
| 5. Matching | Linking + level rules (incl. the open points listed at the end of §11.4), code-only types, deduped chunked linking, caches with evidence_set_hash and version hash (`met`-only reuse), bands, seniority, gaps aggregation, targeted rematch, staleness and lazy re-screen, `explain_match`, `ask_posting` statuses, `analyze_posting` (pasted text, private jobs); `review_jobs`, instructions, `get_workflow_instructions`, skill | Review flow complete in client and Claude Code; matching eval on dev split | 12 |
| 6. Decisions & drafts | `record_decision`, `list_jobs` (incl. `filtered` and `stale`), exclusions, LangGraph draft workflow + checkpointer + lease + resume + thread cleanup, `drafts`, guidelines, screening answers, safety net, gaps as arguments | Full flow including approved draft | 12 |
| 7. Complete evals & observability | Complete datasets, binary rubrics, judge (+ judge-agreement experiment), eval cache, budget guard, experiments, test-split run, Opik complete, README figures | Eval report and figures | 10 |
| 8. Production | Descope fail-closed, usage limits, Azure (Postgres, secrets, CD with OIDC, startup lock), `delete_my_data` (incl. pasted jobs and LangGraph threads), privacy, Host/Origin guard, Claude Desktop remote connector; optional SBOM/image scan | Live demo URL with auth | 10 |
| 9. Delivery | README from the course template (hosts configs, capability channels, features, limitations, privacy, GeoNames attribution), fresh-clone test as an evaluator, submission `.txt` | Submitted | 5 |
| **Total** | | | **~106** |

---

## 22. To verify during the spikes

- Python 3.14 wheels for every dependency (incl. psycopg 3 binary); LiteLLM version resolved in `uv.lock`; FastMCP 3.x latest patch still maintained, and its API for custom routes, auth providers, `stateless_http` (passed to `run()`/`http_app()`), progress, annotations, `strict_input_validation`, `host_origin_protection`.
- `gpt-6-luna` and judge candidates (e.g. `gpt-6-sol`, `gpt-6.1-sol`): current names and prices; Responses API function calling with reasoning effort; temperature support; strict structured output constraints; `prompt_cache_key`; cache-write pricing.
- `ChatOpenAI` with `use_responses_api=True`; Opik integration with LangChain/LangGraph; LangGraph Postgres checkpointer on psycopg 3: `setup()` under the advisory lock, resume with `invoke(None)`, thread deletion.
- Host tool timeouts (Cursor, Claude Code, Claude Desktop, from Windows to WSL2/Docker) and real screening and draft latency → set `SCREEN_ROUND_SECONDS` so a call stays under half the smallest timeout (the funnel stores `screen_ms` per run), `CLAIM_STALE_SECONDS`, `DRAFT_LEASE_SECONDS`, and whether drafts need bounded steps.
- FastMCP with `stateless_http=True`: progress notifications reach the client; `ctx.session_id` behaviour.
- SerpApi Google Jobs response fields in Argentina (`via`, description length, apply links); free plan limits.
- ~~Get on Board current API endpoints, fields and terms~~ (verified in phase 2, see §10).
- GeoNames `cities500` file, size and license terms; `geo_places` load time.
- Postgres major supported by Azure Flexible Server; Azure Container Apps free grant; Descope plan.

---

## 23. Glossary

- **Job**: a job posting (never a background task; CV work history is `experience`). **Canonical job**: the first-seen row of a duplicate group; `job_id` always refers to it.
- **Run**: one search (`search`) or one job screened alone (`single`), with its `run_jobs` rows; users never see the term.
- **Position**: run-scoped display number in a shortlist ("the 3"); tools never accept it.
- **Card**: compact representation of a job in a shortlist.
- **Evidence / evidence ID**: a labelled item (E1…) from the CV or the user that can support a requirement; the LLM refers to evidence only by ID.
- **Link**: the LLM's statement that an evidence item relates to an atom of a requirement (`direct` / `related`); levels are computed by code.
- **Atom**: one thing a requirement asks for (a technology, tool, practice or kind of experience); requirements are split into atoms once per job.
- **Explicit / inferred restriction**: stated in the posting vs deduced from indirect signals.
- **Profile question**: a question to the user when a restriction depends on a profile field they have not answered yet.
- **Filtered / discarded**: discarded automatically by prefilters or eligibility / discarded by the user.
- **Claim**: marking a job as being processed by one `screen_batch` call.
- **Lease**: time-limited ownership of a draft execution stored in the database.
- **Screening hash**: hash of the profile inputs that affect screening, stored per `run_jobs` row to detect stale results.
- **Version hash**: automatic version of an LLM-dependent cache, derived from prompt + examples + schema + model + model parameters.
