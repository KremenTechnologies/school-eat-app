.PHONY: install run test

install:
	uv sync

run: install
	uv run --env-file .env uvicorn app.main:app --reload --port 8000

# Needs a THROWAWAY Postgres — the fixture drops & recreates every table.
# Never point this at the production DB in .env.
#   TEST_DATABASE_URL=postgresql://postgres:pg@localhost:5433/t make test
test: install
	@test -n "$$TEST_DATABASE_URL" || { echo "set TEST_DATABASE_URL to a throwaway Postgres"; exit 1; }
	TEST_DATABASE_URL="$$TEST_DATABASE_URL" SMS_DEBUG=1 SESSION_SECRET=test uv run pytest -q
