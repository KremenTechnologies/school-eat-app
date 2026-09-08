# school-eat-app

Веб-застосунок для школи: облік відвідування учнів по класах і щоденні заявки
на харчування (сніданки/обіди), зі сповіщеннями в Telegram. Інтерфейс — українською.

- **Бекенд:** FastAPI + PostgreSQL (`psycopg`, синхронний).
- **Фронтенд:** односторінковий застосунок (vanilla JS, без збірки), який
  віддається з `/` і працює через `/api/*`.
- **Автентифікація:** сесійна cookie; вхід за телефоном + «Прізвище Ім'я»
  або за одноразовим SMS-кодом (Kyivstar).

## Запуск локально

Потрібні `uv` і доступ до PostgreSQL.

```bash
cp .env.example .env      # заповнити DATABASE_URL, SESSION_SECRET, DEV1/DEV2, за потреби Kyivstar
make run                  # http://127.0.0.1:8000
make test                 # ⚠️ дропає й перестворює всі таблиці в базі з .env
```

У `.env` кожне значення має бути в лапках (парсер `uv --env-file`).
Таблиці та початкові дані (класи 1-А…9-В, два акаунти розробника з `DEV*`)
створюються автоматично при старті.

## Ролі

| Роль | Доступ |
|------|--------|
| `developer` | усе; єдиний, хто створює користувачів і адміністраторів |
| `admin` | усі функції та звіти, може додавати вчителів |
| `teacher` | лише дані власного класу |

## Змінні середовища

| Змінна | Призначення |
|--------|-------------|
| `DATABASE_URL` | рядок підключення до PostgreSQL |
| `SESSION_SECRET` | ключ підпису сесійної cookie |
| `DEV1_PHONE`, `DEV1_NAME`, `DEV2_PHONE`, `DEV2_NAME` | акаунти розробника, що сідяться при старті |
| `SMS_DEBUG` | `1` — друкувати OTP у лог замість надсилання |
| `KYIVSTAR_SMS_ENABLED` | `true` — вмикає реальне надсилання SMS |
| `KYIVSTAR_CLIENT_ID`, `KYIVSTAR_CLIENT_SECRET`, `KYIVSTAR_SENDER` | доступ до Kyivstar SMS API |

Telegram `bot_token` / `chat_id` зберігаються в БЗ (таблиця `settings`) і
редагуються у вкладці «Налаштування», а не через env.

## Деплой (render.com)

`render.yaml` описує web-сервіс (Python). Postgres — зовнішній, `DATABASE_URL`
задається вручну в дашборді разом із `DEV*` та `KYIVSTAR_*`; `SESSION_SECRET`
генерується автоматично.

```
startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Структура

```
app/
  main.py       FastAPI, lifespan (схема + сіди), віддача SPA
  db.py         пул psycopg, init_schema(), seed_classes(), seed_developers()
  auth.py       сесія, нормалізація телефону/імені, залежності ролей
  sms.py        життєвий цикл OTP (login_codes)
  kyivstar.py   клієнт Kyivstar SMS API
  telegram.py   надсилання в Telegram Bot API
  routes.py     усі /api ендпоінти
schema.sql      DDL, виконується при старті
templates/attendance-app.html   SPA
test_main.py    смоук-тест API
```
