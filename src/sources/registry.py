"""Which sources are active: recordings in demo mode, the real APIs otherwise."""

from pathlib import Path

import httpx

from src.config.settings import Settings
from src.sources.base import JobSource
from src.sources.getonbrd import GetOnBoardReplay, GetOnBoardSource

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
GETONBRD_RECORDINGS = FIXTURES_DIR / "getonbrd"


def recorded_pages(directory: Path = GETONBRD_RECORDINGS) -> list[Path]:
    """`page-1.json`, `page-2.json`... in page order (numeric, so page 10 comes after page 9)."""
    return sorted(directory.glob("page-*.json"), key=lambda path: int(path.stem.split("-")[1]))


def build_sources(settings: Settings, client: httpx.AsyncClient) -> list[JobSource]:
    if settings.demo_mode:
        return [GetOnBoardReplay(recorded_pages())]
    return [GetOnBoardSource(client)]
