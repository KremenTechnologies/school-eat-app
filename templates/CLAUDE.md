# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project context and decisions: [../MEMORY.md](../MEMORY.md).

## Commands

Python 3.12+, `uv`. Postgres required (local via Docker, or a remote URL).

```bash
uv sync
uv run --env-file .env uvicorn app.main:app --port 8000   # or: preview_start "school-eat"
DATABASE_URL=postgresql://... SMS_DEBUG=1 uv run pytest    # integration test; skips without DATABASE_URL
```

`.env` (see `.env.example`) — quote every value, uv's env-file parser needs it for non-ASCII.

## Architecture

FastAPI + Postgres. One `<script>` SPA (vanilla JS, no build) served at `/`, talks to `/api/*`.

### Backend (`app/`)
- `db.py` — `psycopg` sync `ConnectionPool` (`DATABASE_URL`), `init_schema()` runs `schema.sql` on startup, `seed_developers()` inserts the two `DEV{1,2}_*` env accounts. `canon_phone()` = last 9 digits (so `+380 67…`, `380…`, `067…` all match).
- `auth.py` — `SessionMiddleware` cookie. `norm_name()` = lowercase, no whitespace. `authenticate(phone, name)`. Deps: `current_user`, `require_priv` (developer|admin), `require_dev`.
- `sms.py` — `login_codes` table, 6-digit code, 5 min TTL, ≤5 attempts, **one code per phone per 5 min** (new request while the old is unexpired → 429).
- `kyivstar.py` — Kyivstar programmable SMS, ported from open-city-atlantis: OAuth2 client-credentials (token cached in-process), `POST {base}/sms` with `{from, to, text, maxSegments:1, messageTtlSec:600}`, phone as `380…` (no `+`). Blank/disabled creds → stub: logs, prints if `SMS_DEBUG`, returns ok. Env: `KYIVSTAR_SMS_ENABLED`, `KYIVSTAR_CLIENT_ID`, `KYIVSTAR_CLIENT_SECRET`, `KYIVSTAR_SENDER`.
- `telegram.py` — server-side Bot API send (HTML). `attendance_message` (fired on every `PUT /api/attendance/...`), `summary_message` (meal table, `POST /api/attendance/summary`), `test_message`. Kyiv time in footers (needs `tzdata`). Pure-function tests in `test_telegram.py`.
- `routes.py` — all `/api` endpoints; roles enforced per route; teachers scoped to their own class.
- `main.py` — app wiring, lifespan, `GET /` → `templates/attendance-app.html`.

### Schema (`schema.sql`)
`users`, `classes` (name pk), `settings` (singleton row), `attendance` (pk `date, class_name`), `login_codes`. No migration tool yet — edit `schema.sql`, it's `CREATE TABLE IF NOT EXISTS`.

### SPA (`attendance-app.html`)
- `api(method, path, body)` — the only transport. No localStorage, no client state persistence.
- Attendance record fields are snake_case and match DB columns (`illness_count`, `no_reason_names`, …).
- Login screen: "За прізвищем" (phone + name) / "За SMS-кодом" tabs. No first-run bootstrap.
- Client keeps display-only logic: `computePresent`, `mealDefaults` (grades 1–6,9 breakfast / 7–8 lunch), monthly absence aggregation.
- Tabs: `attendance`, `report`, `monthly`, `meals`, `history`, `settings` (isPriv).

## Deploy (render.com)
`render.yaml` — web (python) + free Postgres. `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`. `requirements.txt` mirrors `pyproject.toml` (render doesn't read `uv.lock`). Set `DEV{1,2}_PHONE/NAME` in the dashboard.
