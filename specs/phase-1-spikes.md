# Phase 1 — Risk spikes

**Goal:** find out, cheaply and before building, whether the risky assumptions of `specs/system.md` hold. Every spike has numeric go/no-go thresholds and a plan B, written **before** running it.

**Timebox:** 1.5× the estimate of each spike; if exceeded, stop and decide with what was measured.
**Code:** `spikes/<n>-<name>/` is a local notebook, git-ignored and never committed, each with a short `RESULTS.md` (measured vs threshold, go/no-go, decision). What a spike proves ends up in the repo only as project files (config, `src/`, tests, fixtures) and one-line decisions in `CLAUDE.md`.
**Order:** 1.1 → 1.2 → 1.3 (no LLM) → 1.4 → 1.3b → 1.5 → 1.6 → 1.7 → 1.8.

## Prerequisites (carried over from phase 0)
- [ ] OpenAI, SerpApi and Opik keys in the real `.env` (needed from 1.3b / 1.4)
- [ ] Azure budget alert created (needed before 1.8)

## 1.1 Dependencies on Python 3.14
- [x] Add runtime and dev dependencies; `uv sync --frozen` works
- [x] Smoke test of imports (`spikes/1.1-deps/smoke_imports.py`)
- [x] LiteLLM check in `uv.lock`; constraint added if present
- [x] FastMCP 3.x latest release date checked

**Go if:** FastMCP `>=3.4.7,<4`, SQLAlchemy 2 async, psycopg 3 (binary), alembic, langgraph + checkpoint-postgres, langchain-core/openai, opik, httpx, pypdf, pydantic-settings and the pytest stack resolve on 3.14 **without compiling from source**; the smoke test passes; LiteLLM is absent from `uv.lock` or outside the compromised versions; last FastMCP 3.x release is ≤ 90 days old.
**Plan B:** no psycopg binary wheel → `psycopg[c]` or pure psycopg + system `libpq`. A package without 3.14 support → pin an older version that has it, or replace it. FastMCP 3.x abandoned → evaluate 4.x and record the decision.

## 1.2 Docker + Postgres + Alembic
- [x] Compose with Postgres; init script creates `laburo` and `laburo_test`
- [x] Alembic up/down/up on a dummy table
- [x] Checkpointer `setup()` after Alembic under one advisory lock
- [x] Alembic autogenerate ignores checkpointer tables

**Go if:** Postgres major = highest one supported by Azure Flexible Server (verified); compose healthy in < 30 s; both databases created; migration up/down/up works; no autogenerate diff from checkpointer tables.
**Plan B:** checkpointer/Alembic conflict → separate Postgres schema for the checkpointer.

## 1.3 Hosts and timeouts (no LLM)
- [x] FastMCP HTTP server with a `sleep(seconds)` tool, with and without progress
- [x] Tool visible and callable in Inspector and Claude Code (Windows → WSL `localhost` works)
- [x] Claude Desktop (Windows Store build, local server via `mcp-remote`): tool visible and callable; its config is read from `%LOCALAPPDATA%\Claude-Data\<package>\`
- [ ] Cursor: deferred until a real problem appears
- [x] Timeouts measured: Inspector 60 s (progress did not extend it by CLI), Claude Code > 90 s
- [x] Claude Desktop timeout: a 70 s `sleep_plain` call completed with no cancellation (upper bound not measured)
- [ ] Cursor timeout: deferred

**Go if:** at least 3 of 4 hosts work and the **smallest measured timeout is ≥ 60 s**.
**Plan B:** a host that does not work is documented as unsupported. Timeout < 60 s → lower `SCREEN_MAX_JOBS_PER_CALL` and make drafts advance in bounded steps from day one.

**Outcome:** conditional GO. Working assumption: smallest host timeout = 60 s, so one call must finish under ~30 s. Revisit when Cursor or Claude Desktop is first used for real.

## 1.4 LLM layer
- [x] `ChatOpenAI` on the Responses API with strict structured output (10 calls)
- [x] Tool calling with reasoning
- [x] `cached_tokens` on a second call with a prefix ≥ 1024 tokens
- [x] Opik: LLM span nested under the tool trace
- [x] Accepted parameters, model names and prices recorded

**Go if:** strict output valid 10/10; tool calling with reasoning works; `cached_tokens` > 0 on the 2nd call; span nesting visible in Opik.
**Plan B:** strict not supported by `ChatOpenAI` → `with_structured_output(method="json_schema")` or a direct call inside `src/llm/`. Opik nesting fails → manual spans in one place.

## 1.3b Draft-like loop latency (needs key)
- [x] Time a 4-call LLM loop through the HTTP server

**Go if:** the whole loop fits under half the smallest host timeout; otherwise bounded steps (see 1.3 plan B).

## 1.5 Idea validation
- [x] 15 real postings, contact data scrubbed, saved in `fixtures/`
- [x] Hand labels (restrictions, explicit/inferred/contradictory, eligible/not/doubtful)
- [x] Extraction run; metrics and cost per job recorded

**Go if:** recall of explicit restrictions ≥ 90 %; explicit/inferred/contradictory correct ≥ 80 %; **0 valid jobs marked `not_eligible`**; ≥ 3/15 postings carry a location restriction the aggregator does not show (proves the problem exists).
**Plan B:** recall < 90 % → few-shots or split prompt, one iteration. Still < 75 % → narrow scope (remote only) and re-plan. < 3/15 hidden restrictions → revisit the core value before phase 2.

**Outcome:** GO. Recall 95% (strict), evidence kind 89%, 0 valid jobs discarded, 8/15 postings with a location restriction the aggregator does not show. Untested: citizenship / work authorization / W2 cases (cover with synthetic eligibility cases).

## 1.6 PDF parsing with pypdf
- [x] Fictional sample CV created in `data/samples/`
- [x] Test set: sample CV, real CV, and 3 hard layouts (two-column, design-tool export such as Canva, image-only scan)
- [x] Parse in a subprocess with timeout on every PDF of the set
- [x] Unreadable detection: characters per page (scan) **and** share of readable words (garbled text from fonts without a Unicode map)
- [x] Evidence and language-level quality checked
- [x] ~~Optional probe~~ skipped on purpose: vision is only explored if failures show up, and after pdfminer.six 0 of 4 text-based CVs failed

**Go if:** text extracted in < 5 s; timeout kills the process; scanned **and** garbled PDFs detected (0 bad texts reach the profile); ≥ 90 % of experiences/skills extracted vs a manual count on text-based CVs; language levels correct.
**Plan B:** broken layout with pypdf → `pdfminer.six` (MIT). Never PyMuPDF.
**Plan C (vision):** if, after Plan B, ≥ 2 of the 4 text-based CVs are still unreadable or < 90 %, bring vision into v1 as a fallback that only **transcribes** pages into `cv_files.extracted_text` (normal pipeline after it, user confirms at the `build_profile` stop). Otherwise vision stays in the roadmap and `CV_SCANNED` / `CV_UNREADABLE` tell the user how to export a text PDF.

## 1.7 Linking + level rules
- [x] 5 jobs, ~30 requirements labelled (35, plus 23 on 2 held-out postings)
- [x] Link requirements to evidence; compute levels in code
- [x] 3 runs for stability

**Go if:** **0 false `met`**; level accuracy ≥ 80 %; ≥ 90 % identical results across 3 runs.
**Plan B:** chunk size 1, few-shots, or a larger model override for linking only.

**Outcome:** GO with a redesigned contract. Three designs judged compound-requirement coverage inside the prompt and failed (too cautious, too generous, or unstable). Final design: requirements split once per job into atoms; the LLM links atoms with `direct`/`related` (only `direct` counts); code computes levels and combines atoms; new `weak` evidence strength. Main set (31): 0 false `met`, accuracy 84–87 %, 93 % stable (one label changed after seeing results, recorded). Held-out postings 05 and 12 (20): 0 false `met`, 90 %, 94 %. Open: requirement-side qualifiers ("advanced") are not checked by code; SQL ↔ PostgreSQL judged `related` (cautious); split stability unmeasured; one profile and model.

## 1.8 Azure hello-world
Requires the Azure budget alert.
- [x] Hello-world MCP on Container Apps with `stateless_http=True` over HTTPS (Brazil South, 0.25 vCPU, image from public GHCR)
- [x] Progress notifications received by Claude Code (interactive shows 1/10, 2/10…; not visible in the `claude -p` event stream; an MCP client received 5/5)
- [x] `ctx.session_id` behaviour documented: a new id on every call in stateless mode, locally and behind the ingress
- [x] Cold start measured: 25.7 s and 23.4 s (2 samples after scale to zero); warm 0.24–0.27 s

**Go if:** reachable over HTTPS from Claude Code; progress notifications arrive; cold start < 30 s.
**Plan B:** progress does not arrive in stateless mode → rely on short calls only (already the design). Not enough credits → Postgres on Neon, app still on Container Apps.

**Outcome:** GO. Reachable over HTTPS from Claude Code; progress arrives; cold start < 30 s but with little margin: a request that wakes a scaled-to-zero app pays ~25 s, which can stack on a ~30 s tool call. Resources deleted after the spike.

## Definition of done
- [ ] Each spike has a local `RESULTS.md` with go/no-go against the thresholds above
- [x] Scrubbed fixtures and first dev/test labels saved (`fixtures/postings/getonbrd/`, `evals/datasets/{dev,test}/`, `data/samples/sample_evidence.json`; PII test in `tests/unit/`)
- [ ] New decisions added as one line in `CLAUDE.md`; `system.md` updated where a contract changed
- [ ] PR to `main`; **Current phase** updated to 2

Stopped at: all spikes done (1.1–1.8 GO); DoD items 1–3 done; spike archive on the orphan `spikes` branch. Next: PR to `main` and **Current phase** → 2.
