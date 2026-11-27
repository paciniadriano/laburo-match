"""`/health` and `/ready` called over HTTP, with the app's lifespan running."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config.settings import Settings
from src.server import create_mcp_server

SETTINGS = Settings.from_env_file(None)


async def _get(engine: AsyncEngine, path: str) -> httpx.Response:
    app = create_mcp_server(SETTINGS, engine=engine, sources=[]).http_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            return await client.get(path)


async def test_health_is_ok(engine: AsyncEngine):
    response = await _get(engine, "/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_when_the_database_answers(engine: AsyncEngine):
    response = await _get(engine, "/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_not_ready_when_the_database_is_down_but_still_alive():
    dead = create_async_engine("postgresql+psycopg://x:x@127.0.0.1:1/none")
    assert (await _get(dead, "/ready")).status_code == 503
    assert (await _get(dead, "/health")).status_code == 200
    await dead.dispose()
