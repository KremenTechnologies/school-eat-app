# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Python 3.12+, managed with `uv` (see `uv.lock`).

```bash
uv sync                          # install deps into .venv
uv run uvicorn main:app --reload # run API on http://127.0.0.1:8000
```

`test_main.http` holds HTTP-client requests (PyCharm/IDEA) for smoke-testing endpoints. There is no test suite or linter configured yet.

## Architecture

Two pieces that are **not wired together yet**:

- `main.py` — FastAPI stub with two hello-world routes. It does not serve `templates/` (no Jinja2/StaticFiles). Any backend work starts here.
- `templates/attendance-app.html` — the actual product: a single-file, Ukrainian-language SPA (vanilla JS, no build step) for school attendance and meal requests. Everything below lives in its one `<script>`.

### The SPA (`attendance-app.html`)

- **Storage abstraction**: all persistence goes through `window.storage.{get,set,delete,list}` (async, key/value, `list(prefix)`). A `localStorage` shim is installed only if `window.storage` is absent — this is the seam for swapping in a server-backed store via the FastAPI app.
- **Keys**: `classes`, `users`, `settings` (Telegram `botToken`/`chatId`), `session` (JSON blobs), and one record per class-day at `att_<YYYY-MM-DD>_<encodeURIComponent(class)>` (see `attKey`). History/report views enumerate dates by `list("att_")`.
- **Roles**: `developer` (created via first-run bootstrap screen), `admin`, `teacher` (bound to one `className`). `isPriv()` = developer or admin; teachers only see their own class. Login is phone number + full name as password (normalised by `normPhone`/`normPass`).
- **Routing**: a single `state` object + `render()` switch over `state.tab` (`attendance`, `report`, `monthly`, `meals`, `history`, `settings`). Each tab has a `renderX()` that writes innerHTML into `#view` and rebinds handlers. Per-date records are cached in `state.dateCache`; call `invalidateDateCache(date)` after writes.
- **Meal rules**: `BREAKFAST_ONLY_GRADES` / `LUNCH_ONLY_GRADES` drive defaults in `mealDefaults`; grade is parsed from the class name (`parseGrade`, e.g. "5-А" → 5).
- **Telegram**: `sendTelegram` posts directly to the Bot API from the browser using settings stored in the app.
