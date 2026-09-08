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
- На старті також `seed_classes()` — 29 класів (1-А … 9-В + «Індивідуальне навчання 9-В»), список у `db.SEED_CLASSES`, `ON CONFLICT DO NOTHING`.
- `templates/attendance-app.html` — SPA без localStorage; єдиний транспорт `api()` → `/api/*`. Поля запису відвідування = колонки БД (snake_case: `illness_count`, `no_reason_names`…).
- Тест: `test_main.py` (pytest + `TestClient`), проходить проти Postgres у `DATABASE_URL`; без нього — skip. Локально ганяв через `postgres:16-alpine` у colima.

### Автентифікація
- Двоє **developer**-акаунтів сідяться при старті з env `DEV{1,2}_PHONE/NAME` (`ON CONFLICT DO NOTHING`). Реальні значення — [seed-developers](seed-developers.md), не в git.
- Користувачів/адмінів створює **лише developer** (admin не може створити admin). Bootstrap-екрана нема.
- Логін: телефон + ім'я та прізвище. Телефон → останні 9 цифр (`canon_phone`), тому `+380 67…`, `380…`, `067…` збігаються. Ім'я — `norm_name` = `" ".join(sorted(lower().split()))`: регістр і **порядок слів** не важливі, слова розділяються пробілом (між частинами має бути пробіл).
- SMS-вхід: `login_codes`, `/api/login/sms/{request,verify}`, 6 цифр, TTL 5 хв, ≤5 спроб, **1 код на номер раз на 5 хв** (повторний запит → 429). Відправка — `app/kyivstar.py` (порт із open-city-atlantis: OAuth2 client_credentials, `POST {base}/sms`, токен кешується в пам'яті). Порожні креди → стаб (лог + друк при `SMS_DEBUG`). Env: `KYIVSTAR_SMS_ENABLED / CLIENT_ID / CLIENT_SECRET / SENDER`.
- Сесія — підписана cookie (`SessionMiddleware`, `SESSION_SECRET`).
- Telegram шле сервер (`httpx`), токен у Бові `settings`, не в браузері.

### Правила (лишились клієнтські, суто відображення)
`present = registered − abroad − individual − Σ(absence_count)`. Сніданок класам 1–6,9; обід — 7,8 (грейд із назви класу).

## Деплой

`render.yaml` (web python + `databases: free`), `requirements.txt` (render не читає `uv.lock`), `SESSION_SECRET` через `generateValue`, `DEV*` — вручну в дашборді. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## Локальний запуск

`make run` (= `uv run --env-file .env uvicorn app.main:app --reload`), `make test`, `make install`.

`.env` (gitignored, справжній) вже вказує на спільну dev-базу `opencity.psql.tools:10051` / `school_eat_app_db`. Той сервер **відхиляє SSL** → у `DATABASE_URL` без `sslmode=require`. `.env.example` — плейсхолдери. Лапки на кожному значенні обов'язкові (парсер uv).

`make test` дропає й перестворює всі таблиці в базі з `.env` (або `TEST_DATABASE_URL`), тож після нього треба перезасіяти: `uv run --env-file .env python -c "from app import db; db.pool.open(); db.init_schema(); db.seed_developers()"`.

## Репозиторій

`git@github.com:KremenTechnologies/school-eat-app.git`, гілка `main`. Ще не запушено.
