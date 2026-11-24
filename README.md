# laburo-match — spike archive

Archive of the phase 1 risk spikes: the throwaway code, data and notes behind the decisions in `CLAUDE.md`
and `specs/system.md` on `main`. This branch is orphan on purpose: it shares no history with the product code
and is never merged. Each `spikes/<n>-<name>/RESULTS.md` has the go/no-go against thresholds written before running.

| Spike | Question |
|---|---|
| 1.1-deps | Do all dependencies install on Python 3.14 without compiling? |
| 1.2-postgres | Docker Postgres, Alembic and the LangGraph checkpointer side by side |
| 1.3-hosts | Which MCP hosts connect over HTTP, and what are their tool timeouts? |
| 1.4-llm | ChatOpenAI on the Responses API: structured output, accepted params, caching, Opik |
| 1.5-validation | Do real postings hide location restrictions the aggregator does not show? |
| 1.6-pdf | CV text extraction, unreadable-PDF detection and extraction quality |
| 1.7-linking | Can an LLM link requirements to evidence without false `met`? (final design: atoms + direct/related) |
| 1.8-azure | Stateless FastMCP on Azure Container Apps: HTTPS, progress, session id, cold start |

Excluded on purpose: the author's real CV and everything derived from it, and raw API captures.
The fixtures and labelled datasets that came out of the spikes live on `main` (`fixtures/`, `evals/datasets/`).
