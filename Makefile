# Daily commands. Targets are added as the pieces they run are built.
.PHONY: setup db psql up down dev migrate seed test test-fast lint format

setup:  ## Install dependencies exactly as locked and enable the git hooks
	uv sync --frozen
	uv run pre-commit install

db:  ## Start only Postgres (databases `laburo` and `laburo_test`)
	docker compose up -d --wait db

psql:  ## Open a SQL prompt on the dev database (type \q to leave)
	docker compose exec db psql -U laburo -d laburo

up:  ## Build and start Postgres + the MCP server in Docker (waits until healthy)
	docker compose up -d --build --wait

down:  ## Stop the containers (the database volume is kept)
	docker compose down

dev:  ## Run the MCP server locally over HTTP on localhost:8000 (needs `make db` and `make migrate`)
	uv run python -m src.main

migrate:  ## Apply migrations to the dev database (same routine as container start)
	uv run python -m src.db.startup

seed:  ## Load the fictional sample profile into the dev database (idempotent)
	uv run python -m scripts.seed_profile

test:  ## All tests on the laburo_test database ($0, no keys)
	uv run pytest

test-fast:  ## Tests that need no database
	uv run pytest tests/unit

lint:  ## ruff + pyright
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

format:  ## Apply ruff formatting and safe fixes
	uv run ruff check --fix .
	uv run ruff format .
