# laburo-match

> *"Laburo" is Argentine slang for "job".*
> An MCP server that finds remote, hybrid and on-site jobs, tells you which ones you can actually apply to from where you live, measures how well you fit each one with cited evidence, and helps you prepare the application without inventing anything.

Capstone project for the Agentic AI Engineering course (MCP server track). The full system specification lives in `specs/system.md`; read it when you need details. This file holds the rules, conventions and decisions that apply to every session. Testing rules live in `.claude/rules/testing.md` and load when working on tests, evals or fixtures.

**Current phase: 2 — Vertical slice**

---

## How we work (spec-driven, lightweight)

- `specs/system.md` describes **what** the system does: tools, flows, data model, pipelines, evaluation.
- `specs/phase-N-<name>.md` is created **at the start of each phase**, in plan mode: goal, tasks as checkboxes, definition of done. Spike phases also write numeric go/no-go thresholds and a plan B per spike **before** running them. Timebox: 20–30 minutes.
- This file is the **only** place for decisions (one line each: decision → reason).
- **Reality beats the spec.** If a spike, test or eval contradicts the spec, follow the evidence and update the spec afterwards.
- Update a spec **only when a contract changes** (tool signature, DB schema, flow behaviour), in the **same commit** as the code change. Bug fixes and refactors do not touch specs.
- Small changes (typo, failing test, rename) do not need plan mode.

### Session rules
1. At the start of a session: read the spec of the **current phase** (above) and continue from the first unchecked task.
2. A task is done when its test passes and its checkbox is ticked in the phase spec.
3. At the end of a session: tick completed boxes and add a one-line `Stopped at: …` note at the bottom of the phase spec.
4. When a phase ends: update **Current phase** in this file.
5. Show evidence (test output, command results), do not just claim success.

---

## Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.14: `uv init --python 3.14.0 .` (course requirement), then `.python-version` = `3.14` and `requires-python = ">=3.14,<3.15"`; Docker and CI use the same minor |
| Package manager | uv; `uv.lock` committed; installs always `uv sync --frozen` |
| MCP | FastMCP 3.x, pinned (`fastmcp>=3.4.7,<4`); follow the FastMCP 3.x docs, not the course code |
| Transport | Streamable HTTP only (local Docker and Azure). In-memory transport for tests, evals and the client in dev |
| Database | PostgreSQL, same major locally, in CI and in Azure; SQLAlchemy 2 async + psycopg 3 (`postgresql+psycopg`); Alembic migrations |
| LLM access | `ChatOpenAI` from `langchain-openai` (only `langchain-core` + `langchain-openai`), OpenAI Responses API |
| Workflow engine | LangGraph functional API, **only** for the draft workflow; Postgres checkpointer (psycopg 3) |
| Observability | Opik (optional at runtime: the server works without a key) |
| HTTP | One shared `httpx.AsyncClient` with timeouts |
| PDF | `pdfminer.six` (MIT, `>=20251230`), parsed in a subprocess with a timeout. Never PyMuPDF (AGPL) |
| Geography | GeoNames `cities500` snapshot (CC BY), loaded into Postgres |
| Quality | ruff, pyright (basic), pre-commit, gitleaks |
| Tests | pytest, pytest-asyncio, respx, real Postgres (separate test database) |
| Deploy (phase 8) | Azure Container Apps, image in GitHub Container Registry, GitHub Actions CI/CD with OIDC |

### Models
- `LLM_BASE_MODEL=gpt-6-luna` → every task, unless a task in `LLM_TASKS` declares an override.
- `LLM_CLIENT_MODEL` → terminal client ReAct loop (empty = base model).
- `LLM_JUDGE_MODEL` → eval judge only (empty = base model). A larger model such as Sol is a candidate, not a rule.
- Model names, prices and parameter support change: verify against current OpenAI docs before relying on them.

---

## Environment

- Development runs inside **WSL2 (Ubuntu)**. The repo lives in the Linux filesystem (`~/projects/laburo-match`), never under `/mnt/c`.
- `.gitattributes` forces LF line endings.
- **No secrets in the project folder.** The real `.env` lives outside the repo (e.g. `~/.config/laburo-match/.env`) and is found through `ENV_FILE_PATH`. The repo only contains `.env.sample` with fake values (course requirement).
- Windows hosts (Claude Desktop, possibly Cursor) reach the server through `localhost`. In the container the server binds `0.0.0.0` and compose publishes `127.0.0.1:8000:8000`; `make dev` binds `127.0.0.1`.
- `DEMO_MODE=true` in the local `.env` until phase 4, to protect the SerpApi quota.

---

## Commands (Makefile)

| Command | What it does |
|---|---|
| `make setup` | `uv sync --frozen`, install pre-commit hooks |
| `make up` / `make down` | Start / stop Postgres + MCP server with Docker Compose |
| `make db` | Start only Postgres (dev and `laburo_test` databases) |
| `make dev` | Run the server locally with `uv run` over HTTP on `localhost:8000` (needs `make db`) |
| `make migrate` | Apply Alembic migrations, the checkpointer setup and the GeoNames load |
| `make client` | Run the terminal MCP client |
| `make test` | All tests (unit, integration, contract, e2e with fakes) on `laburo_test`. $0, no keys |
| `make test-fast` | Unit + contract tests, no DB |
| `make lint` | ruff + pyright |
| `make eval` | Evals on the dev split (manual only; costs money; $0.50 per run by default, `--budget` overrides). `make eval-test` runs the held-out split at milestones |
| `make record-fixtures` | Call real source APIs once, scrub contact data, save fixtures (manual only; counts against the SerpApi cap) |
| `make scrub-fixtures` | Scrub contact data from fixtures added by hand |
| `make update-geonames` | Download a fresh GeoNames snapshot and rewrite its `MANIFEST` (manual only) |

---

## Repository layout

```
src/
  server.py              # create_mcp_server(): FastMCP app, lifespan (DB pools, httpx), auth, middleware
  routers/               # MCP contract only: tools.py, resources.py, prompts.py, ui.py (custom HTTP routes); context.py (AppState, user session), error_mapping.py
  tools/                 # one file per tool, written as the ordered steps of that tool (see Code conventions)
  resources/             # one file per MCP resource (phase 5)
  app/                   # business logic by domain, with its own SQL: profile/, search/, jobs/, eligibility/, matching/, qa/, drafting/, geo/
  sources/               # source adapters (google_jobs, getonbrd)
  llm/                   # tasks.py (LLM_TASKS registry), runner.py (llm.run), messages.py, versioning.py, openai_backend.py, prompts/ (one file per LLM task), eval cache
  models/                # Pydantic contracts: LLM outputs, profile blocks, tool I/O schemas
  db/                    # database infrastructure only: base, session, models/ (the tables), migrations, startup
  prompts/               # host-facing only: MCP prompt texts, shared workflow fragments, application_guidelines.md (LLM task prompts live in llm/prompts/)
  config/                # settings.py (pydantic-settings), constants.py, data/{locations,levels,known_sites,role_families}.py
  core/                  # errors.py, logging.py, observability.py, usage.py (costs/limits), clock.py, security.py
  ui/upload.html         # CV upload page (plain HTML + vanilla JS)
data/geonames/           # pinned GeoNames snapshot + MANIFEST (refreshed manually)
data/samples/            # fictional CV (PDF) and sample profile
client/                  # terminal MCP client (ReAct loop, commands, display)
tests/                   # unit/, integration/, contract/, e2e/, fakes/, factories.py
evals/                   # datasets/{dev,test}/, metrics/<metric>/, run_eval.py
fixtures/                # recorded API responses and pasted postings, contact data scrubbed (shared by tests, evals, demo mode)
scripts/                 # fixture scrubbing, GeoNames snapshot update
specs/                   # system.md + one spec per phase
alembic/                 # migrations
.claude/                 # settings.json (permission allowlist), rules/testing.md, skills/laburo-match/SKILL.md
```

---

## Code conventions

- All code, comments, docs and commit messages in **English**. Server messages (errors, hints, disclaimers) are in English too; the host translates them.
- **Readable over clever.** Small functions, explicit names, docstrings that explain the *why* of the current design (never the history of how we got there).
- Three layers: `routers/` (MCP contract and docstrings for the LLM) → `tools/` (orchestration) → `app/` (logic and API clients). Routers never contain logic.
- **A `tools/` file reads as the ordered steps of the tool** (validate → call named functions → shape the result). Any step longer than a few lines becomes a function in `app/<domain>/`, named for what it does, so the tool stays short and each piece is testable alone.
- **SQL lives with its domain** (`app/jobs/store.py`, `app/search/runs.py`), never in `tools/` or `routers/`. `db/` holds no queries. `models/` are Pydantic contracts; `db/models/` are the tables. Helpers used by several domains go in `core/`, never imported sideways from another domain.
- **Tool parameters use simple types**: `str`, `int`, `bool`, `list[str]`, `Literal[...]`, with defaults instead of `None`. No `Optional`, no unions. A contract test enforces it on input schemas.
- Tools exchange **IDs** (`run_id`, `job_id`), not large text. Results are typed Pydantic models, compact, with a short `next_step_hint`.
- Errors: domain exceptions mapped to `ToolError` with a stable `error_code` and an actionable message. Never return stack traces (`mask_error_details=True`).
- Every tool declares annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). **Annotations and prompts are hints, never security**: every guard is enforced in server code.
- `strict_input_validation=True` on the server.
- **All LLM calls go through `llm.run(task_name, ...)`** using the `LLM_TASKS` registry. No provider SDK imports outside `src/llm/`.
- Prompts are built **stable prefix first, variable content last** (prompt caching). No dates, IDs or user data in the prefix.
- **No server-side state in memory between requests.** Runs, drafts, pending changes and leases live in Postgres.
- All time through `core.clock.now()`, also in SQL: pass `:now` as a parameter, never the database `now()`. All HTTP through the shared client. One DB session per concurrent task (never share a session inside `asyncio.gather`).
- Writes that depend on a version use optimistic concurrency (`UPDATE … WHERE version = :expected`).
- Long-running tools (`screen_batch`, `draft_application`) release their claims or expire their lease in a `finally` when the call is cancelled, inside an `anyio.CancelScope(shield=True)` → FastMCP cancels with anyio scopes, where every `await` in a cancelled scope raises again, so an unshielded cleanup never runs; a test cancels through a scope, because `Task.cancel()` would pass without the shield.
- `user_id` always comes from the auth context (`get_current_user_id()`, `"local"` without auth), never from a tool argument.
- In LangGraph, everything non-deterministic (LLM calls, clock reads) lives inside `@task`.
- No generic repository classes, no DI framework, no Redis, no queues.

---

## Job identity

- **One name everywhere:** a job posting is a `job` in the DB, code, resources and errors. "Job" never means a background task, and CV work history is `experience`, never `job`. Tables `jobs`, `job_extractions`, `run_jobs`; columns `job_id`, `canonical_job_id`; resource `jobs://{job_id}`; error `JOB_NOT_FOUND`. Only exception: the tool names `analyze_posting` and `ask_posting`, which read better for the host LLM.
- **`job_id` = the canonical `jobs.id`** (opaque UUID). Tools only return canonical IDs; a duplicate's ID is resolved to its canonical instead of failing.
- **The canonical never changes:** the first job seen stays canonical. `canonical_job_id` is NULL on canonical rows and duplicates point directly to a canonical (no chains). The best apply route is computed across the group when reading.
- **`decisions` and `drafts`** reference the canonical `job_id`, one row per (user, job) across all runs. Each draft generation increments `drafts.version` and runs on `thread_id = {draft_id}:{version}`.
- **Run-dependent results** (eligibility, fit, gaps, flags) live in `run_jobs` (`run_id`, `job_id`, `user_id`). Readers use the user's most recent `run_jobs` row with `status = done`.
- **Staleness:** each `run_jobs` row stores a `screening_hash` (profile inputs that affect screening: constraints, `evidence_set_hash`, preferences used for fit and seniority). If it differs from the current one, or there is no done row, `explain_match` and `draft_application` re-screen the job as a `single` run (caches keep LLM calls to what changed). `list_jobs` never re-screens; it marks those rows `stale`. `ask_posting` answers from job facts, which do not depend on the user.
- **`analyze_posting`** creates a `single` run too (`search_runs.kind = 'single'`), so every job has a `run_jobs` row and there is one read path. Pasted jobs are private (`jobs.owner_user_id`) and never take part in dedupe.
- **Positions** ("the 3") are run-scoped display numbers. The host maps them to `job_id`; tools never accept positions. A non-UUID `job_id` returns `JOB_NOT_FOUND`: "Pass the job_id from the card, not its position."

---

## Security rules (always)

- Untrusted content (postings, CVs) goes inside clear delimiters and is treated as data, never as instructions.
- Eligibility verdicts are computed in code. LLM output is structured (enums, evidence IDs); quotes and `apply_email` are verified by exact match in code.
- The server never fetches posting URLs: `analyze_posting` takes pasted text; the URL is only a reference.
- CV upload: PDF only, magic bytes, size and page caps, parsed in a subprocess with a timeout, scanned PDFs rejected.
- Local HTTP is exposed only on `127.0.0.1` and uses FastMCP's Host/Origin guard (`host_origin_protection=True`). Production auth (Descope) is fail-closed.
- No PII in logs or traces (`OBS_CAPTURE_PII=false` by default); users appear as an HMAC hash.
- Never scrape or fetch LinkedIn, Bumeran, ZonaJobs, Computrabajo or Indeed; `config/data/known_sites.py` is the single list.
- Jobs pasted with `analyze_posting` are private to their owner.
- Destructive tools need explicit confirmation arguments that posting text cannot produce.
- Eligibility is an estimate from the posting text, never legal advice; outputs say so.

---

## Git workflow

- One branch per phase (`phase-1-spikes`, `phase-2-vertical-slice`, …), PR when the phase is done, merge to `main` with CI green.
- Small commits with clear messages. Never commit secrets, `.env` files or anything git-ignored.
- GitHub Actions pinned by commit SHA; base images pinned by digest.

---

## Decisions (decision → reason)

### Product
- Core value = eligibility from the user's location, not job aggregation → aggregation already exists in several MCP servers; eligibility for candidates outside the hiring country does not.
- v1 targets tech roles (sources, planner, fixtures, evals); the architecture stays domain-agnostic → clear metrics and coherent examples without blocking other domains later.
- Country, citizenships, work authorizations and modalities come from the profile; nothing is hardcoded → works for any country.
- Remote, hybrid and on-site supported; hybrid/on-site require an office within the max commute distance from the user's confirmed home location or in an extra accepted city → covers local markets too. No relocation countries → user decision: out of scope. It is the last, decoupled block of phase 4 → it can be postponed without touching the rest.
- Office locations are normalized by the LLM (city, region, ISO country; a list when the posting names several offices) and resolved with a pinned GeoNames `cities500` snapshot; distance is computed in code; unresolvable locations → `doubtful` → global coverage without hand-made zone tables.
- Hybrid/on-site whose office country is known and differs from the user's country is discarded even if the city is unknown; unknown country or unresolvable city in an acceptable country is `doubtful` → a border cannot be crossed daily, so waiting for a city adds nothing.
- When the source declares modality and country (Get on Board's `remote_modality` and `countries`), the search prefilter discards those jobs as `office_abroad`, before the cap and with no LLM call, unless the prose names a place that may include the user's country ("oficinas de LATAM") → the cap fills with possible jobs; in the demo data 20 of 30 jobs were hybrid in Chile, the model found the office city in only 7 of the 15 it called hybrid, and on the 15 hand-labelled postings the rule removes exactly the two labelled `not_eligible`.
- A search queues every job that passes the filters, most relevant first; `MAX_NEW_JOBS_PER_SEARCH` (300) is only a safety limit → a job seeker wants everything they can apply to; an extraction costs about $0.00024, is paid once per job and is shared by every user, so the count is not what limits the wait.
- Postings of the same opening inside one search (same employer, title and place) keep only the newest (`duplicate`); without an employer name nothing is merged → one opening is one decision; cross-portal and cross-run dedupe stay in phase 4.
- `list_jobs` arrives in phase 2, read-only, with `all` and `filtered` only; the decision statuses join in phase 6 → user decision: once a search queues every possible job, more than the 10 shortlist cards must be reachable, and statuses that cannot have rows yet would only confuse the host.
- Get on Board's `remote_local` is read as remote, never as "must live in our country" → two hand-labelled `eligible` postings are `remote_local`.
- The user's home location is resolved once in setup and confirmed; if it is not in the dataset, the user names the nearest town → ambiguity (many "San Martín") and misses are handled once, not per job.
- A restriction whose quotes the code cannot verify is downgraded to `inferred`, never deleted → it can only make the job `doubtful`: a fake quote must not discard a good job, and removing a real restriction must not promise an `eligible` one.
- Eligibility verdicts have formal definitions: `not_eligible` needs an explicit, uncontradicted restriction the profile does not meet; `eligible` needs all explicit restrictions met plus an explicit compatible location signal; everything else is `doubtful` → testable and never overconfident.
- Inferred restrictions (e.g. US-only benefits) can only make a job `doubtful`; contradictory explicit statements → `doubtful` with both quotes and a question for the recruiter → never discard on guesses.
- Unknown profile fields (`None` = never asked, different from a confirmed empty value) can only produce `doubtful`; the questions are aggregated at the review stop → never discard on missing data, never ask job by job.
- Payroll, citizenship and clearance phrases ("W2 only", "US SSN", "US citizens only", "security clearance") map to required authorizations/citizenships and are compared with the profile → nothing is absolute; it depends on who the user is.
- An explicit "work from anywhere" is a compatible location signal only if nothing else in the posting excludes the user's country; regions such as "Americas" or unknown places stay `doubtful` → the other restrictions of the posting are still judged, so a posting open to everyone cannot hide a restriction that rules the user out.
- An ordinary contract type (contractor, employee) is shown as a badge and never changes a verdict; only US-specific payroll phrases (W2, 1099, SSN) matter, as work-authorization requirements → contract type says nothing about where a person may live; checked on the spike postings, where a plain "contractor" had wrongly kept three valid jobs `doubtful`.
- Rules may only discard when the profile is incompatible; positive verdicts need extraction + deterministic comparison → cheap filters never remove valid jobs.
- The title prefilter discards only through an explicit blocklist of other role families, and only when the title shares no keyword with the target roles or stack; above the cap, jobs are ordered by title relevance and recency and the rest are `over_cap`, not discarded → noise does not eat the cap and synonyms ("UI Developer") are never lost.
- Eligibility is presented as an estimate, never as legal advice → the employer has the final word.
- A years gap yields `partial` **only when evidence of the skill exists** (with gap size small/large); no evidence → `missing`; years are the union of date intervals → users can fight for their strengths without hiding real absences, and overlapping experiences never count twice.
- Languages are matching requirements, not eligibility constraints; levels are compared on CEFR (certificates mapped by table, self-assessed levels marked as such) → speaking a language is a qualification, not a location restriction.
- Drafts may frame and emphasize freely but never state false verifiable facts (years, titles, employers, authorizations, salary) → false facts are checked in interviews and cost the user the job.
- Tone is never moralistic: describe the situation, give strategies → the tool works for the user.
- Fit is shown as bands (High/Medium/Low), not percentages → percentages imply false precision.
- Shortlist order: eligibility → fit band → job age → most useful first.
- The shortlist shows at most 10 cards, with totals for the rest → tool results enter the host's context on every later turn, and one review stop must stay something a person can judge in one pass; the others stay in `run_jobs` for `list_jobs`.
- Best apply route: company/ATS link → `apply_email` (only if stated verbatim) → aggregator link → the most direct route first.
- Agency and ghost-job signals are warnings, never automatic discards → the user decides.

### Sources
- Google Jobs via SerpApi + Get on Board; any other posting is pasted into `analyze_posting` → legal, public, no scraping.
- The server never fetches posting URLs; hosts with web tools may read a page and pass its text, except blocked sites, where the user pastes it → no SSRF surface, no crawler or headless browser; hosts already have web access.
- Get on Board jobs always carry the source name and a link to their `public_url`, and that link is their apply route; our analysis is shown apart and labelled as an estimate; one page at a time, backing off on 429 → its terms require attribution and sending applicants to its page, keep job data as returned and allow 20 requests per 5 s per IP.
- Remotive is not used → its terms (≤ 4 requests/day, no use to collect sign-ups) do not fit a multi-user server.
- SerpApi has a hard monthly cap in code (200 of the 250 free searches); replans and fixture recording count against it → the quota is never exceeded by accident.
- No per-user source settings: location and language come from the profile, categories from the planner, max age from the exclusions → no extra table and no tool to edit it.
- Company research (Tavily, orchestrator-workers) is roadmap, not v1 → not needed for the core value.

### Architecture
- Client = ReAct agent; server = workflows where code controls the path and the LLM does bounded steps → predictable cost, testable, evaluable.
- `search_jobs` (fast) + `screen_batch` (extract, eligibility, matching) instead of one tool per step → fewer agent turns, protected against host timeouts.
- `screen_batch` is idempotent and safe under concurrency: jobs are claimed with `SELECT … FOR UPDATE SKIP LOCKED`, have per-job status and attempts, stale `processing` rows are reset, failures are retried once → partial failures never break a run.
- Design for a 60 s host timeout: one tool call must finish in about 30 s; progress notifications are not relied on to extend it → measured: Inspector cuts at 60 s even with progress, Claude Code waited > 90 s; Claude Desktop (via `mcp-remote`) completed a 70 s call, Cursor not yet measured; on Azure a cold start adds 23–26 s to the first request after idle.
- `screen_batch` is one round bounded by time (`SCREEN_ROUND_SECONDS`, 20 s): a pool of `LLM_CONCURRENCY` workers takes the next job by relevance as soon as one is free, saves each verdict at once, and at the deadline gives the jobs in flight back to the queue without counting an attempt; every round returns the best jobs judged so far and `remaining`, and the host continues only if the user asks → user decision: the first results must arrive within ~30 s, so time, not a job count, is the limit; cached jobs take milliseconds and a round covers them all; a pool never waits for the slowest job of a batch; a failed job is retried once inside the same round.
- Extraction cache also stores `chars_read` (length of the capped text the model saw) → a changed size cap re-extracts only the postings it cut or can now read whole, and never invalidates the ones that fitted either way.
- Job-level facts are extracted once and cached; user-level comparison is code → one LLM call per job regardless of how many users see it.
- Extraction marks each restriction as explicit, inferred or contradictory, with quotes → eligibility precedence rules need it.
- Extraction: one job per LLM call, in parallel with a concurrency limit; batch size is a setting decided by an experiment → isolation and quality; tokens cost the same either way.
- Matching: each requirement is split once per job into atoms (`all`/`any`); the LLM only **links** atoms to evidence IDs with `direct` or `related`, and only `direct` counts; **code** computes each atom's level from relation, evidence strength and years and combines the atoms → semantics where LLMs are strong, arithmetic, thresholds and "is the whole requirement covered" where code is reliable; validated in spike 1.7 on 58 requirements (0 false-`met`, 84–90 % level accuracy, 93–94 % identical across 3 runs), after judging coverage of compound requirements inside the prompt was either too cautious or too generous.
- Evidence strength has three values: `detailed`, `mention` and `weak` (the CV says "basic", "coursework", "familiar with"); weak evidence never gives `met` → a vague claim must not become a verified skill. Qualifiers inside a requirement ("advanced") are not checked by code yet.
- No text fast path and no skill taxonomy → exact-name matching ignores context and taxonomies fail silently; both produced false-`met` results in the experiment.
- CV text comes from `pdfminer.six` as the only engine, with no pypdf fallback; `>=20251230` fixes two deserialization CVEs → pypdf returned the Canva CV in scrambled reading order with no quality signal (5 of 9 bullets under the wrong job), so there is no trigger for a fallback; pdfminer orders text by page position at the same speed.
- CV text quality is checked in code before any LLM call (characters per page, bad-character ratio including `(cid:N)`, share of readable words); thresholds 100 / 5 % / 60 %, language-agnostic → scanned (`CV_SCANNED`) and garbled (`CV_UNREADABLE`) PDFs never reach extraction. Vision/OCR stays in the roadmap: 0 of 4 text-based CVs failed after the engine change.
- Language levels taken from certificates are confirmed by the user, never assigned automatically, and entries are deduplicated per language → real CVs write "exam taken" or "course of CAE", which a certificate-to-CEFR table would overclaim.
- Language, education, soft and condition requirements are resolved in code without the LLM → structured and comparable.
- Atom links are deduplicated across the run, chunked and cached per `(atom_key, evidence_set_hash, version_hash)`; after an evidence change, a cached result is reused only if its level was `met` and every linked evidence item is unchanged and active → new evidence can upgrade a `partial`, removed evidence never leaves a stale `met`.
- LLM cache versions are an automatic hash of prompt + examples + schema + model + model parameters → changing any of them invalidates the cache.
- English as internal pivot language; quotes stay in the original language; drafts in the job's language → bilingual sources, consistent caching.
- Search plan generated by the LLM, validated by code, replanned at most once, not cached → real Plan-and-Execute with one cheap call per search and fresh queries; the plan is stored in `search_runs` for audit.
- LangGraph only for the draft loop (writer → deterministic evidence check → LLM reviewer → editor, capped iterations); the screening pipeline is plain asyncio → a graph only where there is a real cycle.
- Drafts run under a DB lease (one row per user and job); an expired lease is resumed with `invoke(None)` on the same `thread_id`; finished threads are deleted after copying the result to `drafts` → LangGraph persists state but does not prevent duplicate execution or detect crashes, and no PII stays in checkpoint tables.
- If a draft does not fit under half the smallest host timeout, `draft_application` advances in bounded steps and returns `in_progress` → same protection as `screen_batch`; FastMCP background tasks are not used because durable work needs Redis.
- Human feedback in drafts becomes reviews with highest priority → one path for automatic and human corrections.
- Draft approval is data (a saved decision), not a boolean flag → a flag can be faked by the host model.
- `update_profile` is two-step: previews live in `profile_changes`, bound to the `profile_version` they were computed from; a new preview supersedes the previous one and stale previews are rejected (`PROFILE_CHANGED`) → explicit, safe confirmation without elicitation, and every profile write stays optimistic.
- HITL only through MCP prompts and conversation; no elicitation, no sampling → works in every host.
- One review stop per batch, with defaults ("ok") and aggregated gaps and profile questions → feedback must not be annoying.
- Memory in Postgres: semantic (profile, evidence), episodic (decisions, runs), procedural (exclusions confirmed by the user).
- No embeddings in v1 → structured matching is more accurate and explainable here.
- FastMCP 3.x instead of 4.x → stable since Feb 2026 and still patched, more community answers, coding assistants know its API; the server keeps no session state, so a later v4 upgrade is cheap.
- Streamable HTTP only, no stdio, `stateless_http=True` in production (passed to `run()`/`http_app()`); Opik threads use `run_id`/`draft_id`, never the MCP session id → same path everywhere and no dependency on session state.
- psycopg 3 for SQLAlchemy and the LangGraph checkpointer → one driver; checkpointer tables are excluded from Alembic autogenerate and created by `setup()` under the migrations lock.
- `run_jobs` carries `user_id`, kept consistent with its run by a composite FK → every private table has `user_id`: direct ownership checks, indexes and cascades.
- Pasted jobs are private (`owner_user_id`) and stay out of dedupe → a posting a recruiter sent privately is never shown to another user.
- CV enters only through `/upload` with a signed, expiring link generated by `build_profile` → one ingestion path, no arbitrary file reads.
- CV stored in Postgres (`cv_files`), never on the container disk → Azure Container Apps filesystems are ephemeral.
- GeoNames lives in a Postgres table (`geo_places`), not in memory → scale-to-zero cold starts never re-parse ~185k places.
- Deterministic tables are Python modules (`config/data/`), not YAML → typed, testable, no loader.
- One usage/cost module for per-user quotas, global ceiling, SerpApi monthly cap, eval budget and cost display → one mechanism, five uses.
- Migrations, checkpointer setup and the GeoNames load run at container start under one advisory lock → works locally and with multiple replicas.
- Alembic runs on a synchronous engine (same psycopg 3 driver) while the app is async → startup scripts and test fixtures call it where an event loop may already be running, and `asyncio.run` inside it would fail.

### MCP interface
- 12 tools, 2 prompts, 4 resources (see `specs/system.md`).
- Domain errors become `ToolError("[CODE] message")` through a decorator applied by `register_mcp_tools`, not through middleware; the `tools/` functions end in `_tool` so the router's function can carry the public name → FastMCP masks every exception inside the tool call (`mask_error_details=True`), before any middleware runs, so a middleware only ever sees the generic message.
- Workflow recipe lives in one Python function used by the MCP prompts, the `get_workflow_instructions` tool and the server `instructions`; the skill calls the tool → single source of truth.
- Project skill `.claude/skills/laburo-match/SKILL.md` is the entry point ("find me jobs") → course lesson: abilities in MCP, procedures in skills, existing binaries via CLI.
- Anything the model must read also exists as a tool, not only as a resource → resources are host-controlled and unevenly supported.

### LLM
- OpenAI only, through `ChatOpenAI` built in `src/llm/factory.py` → fewest dependencies; changing the model is an env var, changing the provider touches one file.
- Responses API → GPT-6 models support function calling with reasoning only there.
- Base model `gpt-6-luna` for every task, with per-task overrides in `LLM_TASKS` and a separate client model setting → Luna is built for extraction/classification at low cost; drafts or the ReAct client may need a larger model if an eval says so.
- `llm.run` never sends `temperature` and uses reasoning effort `low` or `none` (never `minimal`) → `gpt-6-luna` rejects `temperature` and `minimal` with a 400; strict structured output, tool calling with reasoning and prompt caching (99% of a 3.2k-token prefix cached on the 2nd call) all work on the Responses API.
- Judge = base model by default; a larger model (e.g. Sol) is a candidate, adopted only if a judge-agreement experiment on the dev split justifies it → no cost commitment before evidence.
- No LiteLLM as a direct dependency; current Opik already excludes the compromised versions, and a uv constraint keeps them excluded as defense in depth → LiteLLM was compromised twice on PyPI in 2026.
- Eval criteria are binary (pass/fail) rubrics; deterministic criteria reuse the same functions as the draft reviewer → consistent, actionable, no duplicated logic.

### Quality and operations
- Evaluation starts in phase 1 (idea validation) and grows every phase; datasets split into dev (tuning) and held-out test (milestones only) → no inflated results from tuning on the test set.
- Spikes have numeric go/no-go thresholds and a plan B, written before running them → results cannot move the goalposts.
- Every test gets a strict `FakeLLM` through an autouse fixture, and `llm.run` retries an invalid answer exactly once → no test can reach a real provider by accident, and a failing model cannot loop and burn money.
- Tests use FakeLLM + respx fixtures; one fixture set shared by tests, evals and demo mode → $0 CI, deterministic results.
- Tests run on a separate `laburo_test` database and abort on any other name → the real profile in the dev database is never touched.
- Fixtures from real postings are scrubbed of contact data (script + test) → no third-party PII in a public repo.
- Observability: Opik projects per environment, trace = tool call, LLM spans only from the LangChain tracer, funnel counters stored in `search_runs` → measurable cost and LLM-vs-deterministic share, no duplicate spans.
- No OpenTelemetry, Grafana, Redis, queues or PgBouncer → no benefit at this scale.
- Development in WSL2 → same environment as Docker and Azure; `make` and bash work for everyone.
