"""Spike 1.1: every runtime dependency must import on Python 3.14."""
import importlib
import sys

MODULES = [
    "fastmcp", "pydantic", "pydantic_settings", "httpx", "sqlalchemy.ext.asyncio",
    "alembic", "psycopg", "psycopg_pool", "langgraph.func",
    "langgraph.checkpoint.postgres.aio", "langchain_core", "langchain_openai",
    "opik", "pypdf", "respx", "pytest", "pytest_asyncio",
]

failed = []
for name in MODULES:
    try:
        importlib.import_module(name)
        print(f"ok    {name}")
    except Exception as exc:  # report every failure, not just the first
        failed.append(name)
        print(f"FAIL  {name}: {exc!r}")

print(f"\npython {sys.version.split()[0]} | {len(MODULES) - len(failed)}/{len(MODULES)} imports ok")
sys.exit(1 if failed else 0)
