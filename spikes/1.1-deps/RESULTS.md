# Spike 1.1 — Dependencies on Python 3.14

**Verdict: GO.**

| Threshold | Measured |
|---|---|
| Everything resolves on 3.14 without building from source | 165 packages in `uv.lock`, 0 sdist-only; every `uv add` ran with `--no-build` |
| Smoke test of imports | 17/17 ok on Python 3.14.4 |
| psycopg 3 binary wheel | `psycopg-binary 3.3.9`, `cp314` manylinux wheels |
| FastMCP in `>=3.4.7,<4` | 3.4.11, released 2026-10-20 (31 days, threshold ≤ 90) |
| LiteLLM absent or outside compromised versions | Present via Opik (unpinned): 1.105.7. Compromised: 1.82.7, 1.82.8 (Mar 2026), 1.107.0 (Oct 2026). Constraint added in `pyproject.toml` |

## Notes
- FastMCP 4.2.3 already exists; staying on 3.x is a recorded decision (see `CLAUDE.md`).
- LiteLLM 1.105.7 was uploaded 2026-10-28, after the October incident; 1.107.0 is gone from PyPI. Looks like a clean backport line, but confirm against the project's official advisory before phase 8.
- Versions resolved: sqlalchemy 2.1.9, alembic 1.20.1, langgraph 1.2.24, langgraph-checkpoint-postgres 3.2.1, langchain-openai 1.8.5, opik 2.2.138, pypdf 7.1.1, pytest 9.2.0, ruff 0.17.6, pyright 1.1.414.
