# MEMORY — school-eat-app

Довідка про проєкт для швидкого входження в контекст. Технічні деталі — у [templates/CLAUDE.md](templates/CLAUDE.md).

## Що це

Внутрішній інструмент для школи: облік відвідування учнів по класах + щоденні заявки на харчування (сніданки/обіди), зі сповіщеннями в Telegram. Мова інтерфейсу — українська.

## Ціль

Повноцінний проєкт: **FastAPI-бекенд + віддалена PostgreSQL**, готовий до деплою на **render.com** (Web Service + free Postgres).

## Стан: бекенд зроблено

Початковий PoC (клієнтський `window.storage` на localStorage, клієнтський логін, Telegram-токен у сторінці) **повністю переведено на Postgres**. Костилів не лишилось.

- `app/` — FastAPI, `psycopg` синхронний + пул. Файли: `main, db, auth, sms, telegram, routes`.
- `schema.sql` — `users`, `classes`, `settings` (singleton), `attendance` (pk `date,class_name`), `login_codes`. Виконується на старті (`CREATE TABLE IF NOT EXISTS`). Міграцій нема — правити `schema.sql`.
- `templates/attendance-app.html` — SPA без localStorage; єдиний транспорт `api()` → `/api/*`. Поля запису відвідування = колонки БД (snake_case: `illness_count`, `no_reason_names`…).
- Тест: `test_main.py` (pytest + `TestClient`), проходить проти Postgres у `DATABASE_URL`; без нього — skip. Локально ганяв через `postgres:16-alpine` у colima.

### Автентифікація
- Двоє **developer**-акаунтів сідяться при старті з env `DEV{1,2}_PHONE/NAME` (`ON CONFLICT DO NOTHING`). Реальні значення — [seed-developers](seed-developers.md), не в git.
- Користувачів/адмінів створює **лише developer** (admin не може створити admin). Bootstrap-екрана нема.
- Логін: телефон + «Прізвище Ім'я». Телефон → останні 9 цифр (`canon_phone`), тому `+380 67…`, `380…`, `067…` збігаються. Ім'я → нижній регістр без пробілів (Tinkercad-style; **порядок слів важливий**).
- SMS-вхід закладено: `login_codes`, `/api/login/sms/{request,verify}`, 6 цифр, TTL 5 хв, ≤5 спроб. `sms.py::send_sms()` — стаб (501, або друк у stdout при `SMS_DEBUG=1`). **Реальне API SMS дасть користувач пізніше.**
- Сесія — підписана cookie (`SessionMiddleware`, `SESSION_SECRET`).
- Telegram шле сервер (`httpx`), токен у Бові `settings`, не в браузері.

### Правила (лишились клієнтські, суто відображення)
`present = registered − abroad − individual − Σ(absence_count)`. Сніданок класам 1–6,9; обід — 7,8 (грейд із назви класу).

## Деплой

`render.yaml` (web python + `databases: free`), `requirements.txt` (render не читає `uv.lock`), `SESSION_SECRET` через `generateValue`, `DEV*` — вручну в дашборді. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## Локальний запуск

```bash
uv sync
uv run --env-file .env uvicorn app.main:app --port 8000
```
`.env` (див. `.env.example`) — **лапки на кожному значенні** (парсер uv не любить не-ASCII без лапок). Потрібен Postgres: `docker run -d --name pg -e POSTGRES_PASSWORD=pg -e POSTGRES_DB=school_eat -p 5433:5432 postgres:16-alpine`.

## Репозиторій

`git@github.com:KremenTechnologies/school-eat-app.git`, гілка `main`. Ще не запушено.
