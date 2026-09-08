import re

from fastapi import Request, HTTPException

from .db import pool, canon_phone


def norm_name(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def _user_by_phone(phone: str):
    with pool.connection() as conn:
        return conn.execute(
            "select * from users where phone = %s", (canon_phone(phone),)
        ).fetchone()


def authenticate(phone: str, name: str):
    """Phone + 'Прізвище Ім'я' (Tinkercad-style: case-insensitive, whitespace ignored)."""
    u = _user_by_phone(phone)
    if u and norm_name(name) == norm_name(u["full_name"]):
        return u
    return None


def login_session(request: Request, user) -> None:
    request.session["uid"] = user["id"]


def logout_session(request: Request) -> None:
    request.session.clear()


def current_user(request: Request):
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(401, "not authenticated")
    with pool.connection() as conn:
        u = conn.execute("select * from users where id = %s", (uid,)).fetchone()
    if not u:
        request.session.clear()
        raise HTTPException(401, "not authenticated")
    return u


def require_priv(request: Request):
    u = current_user(request)
    if u["role"] not in ("developer", "admin"):
        raise HTTPException(403, "insufficient role")
    return u


def require_dev(request: Request):
    u = current_user(request)
    if u["role"] != "developer":
        raise HTTPException(403, "developer only")
    return u
