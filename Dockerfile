# Runtime image for the MCP server. Local compose and Azure (phase 8) use this same artifact.
# Both base images are pinned by digest, like a lockfile for images.
FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

FROM python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# A user without privileges: a flaw in the server must not give root inside the container.
RUN useradd --system --create-home --uid 10001 app
WORKDIR /app

COPY --from=uv /uv /usr/local/bin/uv

# Dependencies first: this layer is rebuilt only when the lockfile changes, not on every code edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the code, which changes often. Read-only for the app user (owned by root).
COPY alembic.ini ./
COPY alembic ./alembic
COPY fixtures ./fixtures
COPY src ./src
COPY docker/entrypoint.sh /entrypoint.sh

USER app
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
