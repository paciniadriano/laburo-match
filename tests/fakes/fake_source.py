"""A job source that returns what the test gives it and records what it was asked."""

from src.sources.base import SourceJob, SourceQuery, SourceResult


class FakeSource:
    def __init__(
        self, jobs: list[SourceJob], warnings: list[str] | None = None, name: str = "getonbrd"
    ) -> None:
        self.name = name
        self.jobs = jobs
        self.warnings = warnings or []
        self.queries: list[SourceQuery] = []

    async def fetch(self, query: SourceQuery) -> SourceResult:
        self.queries.append(query)
        return SourceResult(list(self.jobs), list(self.warnings))


class ExplodingSource:
    """A source that breaks its own contract by raising instead of returning a warning."""

    name = "explosive"

    async def fetch(self, query: SourceQuery) -> SourceResult:
        raise RuntimeError("boom")
