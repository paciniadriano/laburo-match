"""Which sources are active: recordings in demo mode, the real APIs otherwise."""

from pathlib import Path

import httpx

from src.config.settings import Settings
from src.sources.base import JobSource
from src.sources.getonbrd import GetOnBoardReplay, GetOnBoardSource

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
GETONBRD_RECORDING = FIXTURES_DIR / "getonbrd" / "page-1.json"


def build_sources(settings: Settings, client: httpx.AsyncClient) -> list[JobSource]:
    if settings.demo_mode:
        return [GetOnBoardReplay(GETONBRD_RECORDING)]
    return [GetOnBoardSource(client)]
