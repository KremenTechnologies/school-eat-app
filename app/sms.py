import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .db import pool, canon_phone

CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5


def send_sms(phone: str, text: str) -> None:
    """Stub. Real provider API wired in later (see MEMORY.md)."""
    if os.environ.get("SMS_DEBUG"):
        print(f"[SMS] {phone}: {text}")
        return
    raise HTTPException(501, "SMS provider not configured yet")


def request_code(phone: str) -> None:
    p = canon_phone(phone)
    with pool.connection() as conn:
        exists = conn.execute("select 1 from users where phone = %s", (p,)).fetchone()
        if not exists:
            raise HTTPException(404, "user not found")
        code = f"{secrets.randbelow(1_000_000):06d}"
        conn.execute(
            "insert into login_codes (phone, code, expires_at, attempts) values (%s, %s, %s, 0) "
            "on conflict (phone) do update set code = excluded.code, "
            "expires_at = excluded.expires_at, attempts = 0",
            (p, code, datetime.now(timezone.utc) + CODE_TTL),
        )
    send_sms(p, f"Код входу: {code}")


def verify_code(phone: str, code: str):
    p = canon_phone(phone)
    with pool.connection() as conn:
        row = conn.execute("select * from login_codes where phone = %s", (p,)).fetchone()
        if not row:
            raise HTTPException(400, "no code requested")
        if row["attempts"] >= MAX_ATTEMPTS:
            raise HTTPException(429, "too many attempts")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "code expired")
        if code.strip() != row["code"]:
            conn.execute("update login_codes set attempts = attempts + 1 where phone = %s", (p,))
            raise HTTPException(400, "wrong code")
        conn.execute("delete from login_codes where phone = %s", (p,))
        return conn.execute("select * from users where phone = %s", (p,)).fetchone()
