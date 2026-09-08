.PHONY: install run test

install:
	uv sync

run: install
	uv run --env-file .env uvicorn app.main:app --reload --port 8000

# Uses TEST_DATABASE_URL if set, otherwise DATABASE_URL from .env.
# WARNING: the test fixture drops and recreates all tables.
test: install
	uv run --env-file .env pytest -q
