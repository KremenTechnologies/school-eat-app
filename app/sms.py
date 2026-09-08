import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from . import kyivstar
from .db import pool, canon_phone

CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5


def request_code(phone: str) -> None:
    """One code per phone per 5 min. Overwrites only once the previous expired."""
    p = canon_phone(phone)
    now = datetime.now(timezone.utc)
    with pool.connection() as conn:
        if not conn.execute("select 1 from users where phone = %s", (p,)).fetchone():
            raise HTTPException(404, "користувача з таким номером не знайдено")
        existing = conn.execute(
            "select expires_at from login_codes where phone = %s", (p,)
        ).fetchone()
        if existing and existing["expires_at"] > now:
            wait = int((existing["expires_at"] - now).total_seconds())
            raise HTTPException(429, f"код уже надіслано, повторіть через {wait} с")
        code = f"{secrets.randbelow(1_000_000):06d}"
        conn.execute(
            "insert into login_codes (phone, code, expires_at, attempts) values (%s, %s, %s, 0) "
            "on conflict (phone) do update set code = excluded.code, "
            "expires_at = excluded.expires_at, attempts = 0",
            (p, code, now + CODE_TTL),
        )
    ok, err = kyivstar.send_sms(p, f"Код входу: {code}")
    if not ok:
        with pool.connection() as conn:
            conn.execute("delete from login_codes where phone = %s", (p,))
        raise HTTPException(502, f"SMS не надіслано: {err}")


def verify_code(phone: str, code: str):
    p = canon_phone(phone)
    with pool.connection() as conn:
        row = conn.execute("select * from login_codes where phone = %s", (p,)).fetchone()
        if not row:
            raise HTTPException(400, "код не запитували")
        if row["attempts"] >= MAX_ATTEMPTS:
            raise HTTPException(429, "забагато спроб, запитайте новий код")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "код прострочено")
        if code.strip() != row["code"]:
            conn.execute("update login_codes set attempts = attempts + 1 where phone = %s", (p,))
            raise HTTPException(400, "невірний код")
        conn.execute("delete from login_codes where phone = %s", (p,))
        return conn.execute("select * from users where phone = %s", (p,)).fetchone()
