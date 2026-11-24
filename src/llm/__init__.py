"""LLM access. Callers use `llm.run("task_name", text)`; no provider import outside this package."""

from src.llm.runner import LLMResult, run, use_backend

__all__ = ["LLMResult", "run", "use_backend"]
