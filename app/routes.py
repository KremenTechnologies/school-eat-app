from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import telegram
from .auth import (
    authenticate, current_user, login_session, logout_session,
    require_dev, require_priv,
)
from .db import pool, canon_phone
from .sms import request_code, verify_code

router = APIRouter(prefix="/api")

ATT_FIELDS = [
    "registered", "abroad", "individual",
    "illness_count", "illness_names", "grvi_count", "grvi_names",
    "family_count", "family_names", "no_reason_count", "no_reason_names",
    "breakfast", "lunch", "signature",
]
INT_FIELDS = {"registered", "abroad", "individual", "illness_count", "grvi_count",
              "family_count", "no_reason_count"}
NULLABLE_INT = {"breakfast", "lunch"}


def _clean_name(s: str) -> str:
    return " ".join((s or "").split())


def _pub(u):
    return {"id": u["id"], "phone": u["phone"], "name": u["full_name"],
            "role": u["role"], "className": u["class_name"]}


# ---------- auth ----------
class LoginIn(BaseModel):
    phone: str
    name: str


class SmsRequestIn(BaseModel):
    phone: str


class SmsVerifyIn(BaseModel):
    phone: str
    code: str


@router.post("/login")
def login(body: LoginIn, request: Request):
    u = authenticate(body.phone, body.name)
    if not u:
        raise HTTPException(401, "невірний телефон або ПІБ")
    login_session(request, u)
    return _pub(u)


@router.post("/login/sms/request")
def sms_request(body: SmsRequestIn):
    request_code(body.phone)
    return {"ok": True}


@router.post("/login/sms/verify")
def sms_verify(body: SmsVerifyIn, request: Request):
    u = verify_code(body.phone, body.code)
    login_session(request, u)
    return _pub(u)


@router.post("/logout")
def logout(request: Request):
    logout_session(request)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    return _pub(current_user(request))


# ---------- classes ----------
class ClassIn(BaseModel):
    name: str


@router.get("/classes")
def list_classes(request: Request):
    current_user(request)
    with pool.connection() as conn:
        rows = conn.execute("select name from classes order by name").fetchall()
    return [r["name"] for r in rows]


@router.get("/classes/refusals")
def class_refusals(request: Request):
    current_user(request)
    with pool.connection() as conn:
        rows = conn.execute("select name, meal_refusal from classes").fetchall()
    return {r["name"]: r["meal_refusal"] for r in rows}


@router.put("/classes/{name}/refusal")
def set_class_refusal(name: str, body: dict, request: Request):
    _scope_class(current_user(request), name)
    n = max(0, int(body.get("meal_refusal") or 0))
    with pool.connection() as conn:
        conn.execute("update classes set meal_refusal = %s where name = %s", (n, name))
    return {"meal_refusal": n}


@router.post("/classes")
def add_classes(body: list[ClassIn], request: Request, _=Depends(require_priv)):
    names = [c.name.strip() for c in body if c.name.strip()]
    with pool.connection() as conn:
        for n in names:
            conn.execute("insert into classes (name) values (%s) on conflict do nothing", (n,))
    return list_classes(request)


@router.delete("/classes/{name}")
def del_class(name: str, _=Depends(require_priv)):
    with pool.connection() as conn:
        conn.execute("delete from classes where name = %s", (name,))
    return {"ok": True}


# ---------- users ----------
class UserIn(BaseModel):
    name: str
    phone: str
    role: str
    className: str = ""


class UserPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    className: str | None = None


@router.get("/users")
def list_users(_=Depends(require_priv)):
    with pool.connection() as conn:
        rows = conn.execute(
            "select * from users order by role, full_name"
        ).fetchall()
    return [_pub(u) for u in rows]


@router.post("/users")
def add_user(body: UserIn, actor=Depends(require_priv)):
    if body.role not in ("admin", "teacher"):
        raise HTTPException(400, "роль має бути admin або teacher")
    if body.role == "admin" and actor["role"] != "developer":
        raise HTTPException(403, "адміністраторів створює лише розробник")
    with pool.connection() as conn:
        if conn.execute("select 1 from users where phone = %s", (canon_phone(body.phone),)).fetchone():
            raise HTTPException(409, "цей номер телефону вже використовується")
        conn.execute(
            "insert into users (phone, full_name, role, class_name) values (%s, %s, %s, %s)",
            (canon_phone(body.phone), _clean_name(body.name), body.role,
             body.className if body.role == "teacher" else ""),
        )
    return {"ok": True}


@router.patch("/users/{uid}")
def patch_user(uid: int, body: UserPatch, actor=Depends(require_priv)):
    with pool.connection() as conn:
        target = conn.execute("select * from users where id = %s", (uid,)).fetchone()
        if not target:
            raise HTTPException(404, "не знайдено")
        if target["role"] in ("admin", "developer") and actor["role"] != "developer":
            raise HTTPException(403, "недостатньо прав")
        sets, vals = [], []
        if body.name is not None:
            sets.append("full_name = %s"); vals.append(_clean_name(body.name))
        if body.phone is not None:
            sets.append("phone = %s"); vals.append(canon_phone(body.phone))
        if body.className is not None and target["role"] == "teacher":
            sets.append("class_name = %s"); vals.append(body.className)
        if sets:
            vals.append(uid)
            conn.execute(f"update users set {', '.join(sets)} where id = %s", vals)
    return {"ok": True}


@router.delete("/users/{uid}")
def del_user(uid: int, actor=Depends(require_priv)):
    with pool.connection() as conn:
        target = conn.execute("select * from users where id = %s", (uid,)).fetchone()
        if not target:
            return {"ok": True}
        if target["role"] in ("admin", "developer") and actor["role"] != "developer":
            raise HTTPException(403, "недостатньо прав")
        if target["role"] == "developer":
            raise HTTPException(403, "обліковий запис розробника видалити не можна")
        conn.execute("delete from users where id = %s", (uid,))
    return {"ok": True}


# ---------- settings ----------
class SettingsIn(BaseModel):
    botToken: str = ""
    chatId: str = ""


@router.get("/settings")
def get_settings(_=Depends(require_priv)):
    with pool.connection() as conn:
        s = conn.execute("select bot_token, chat_id from settings where id = 1").fetchone()
    return {"botToken": s["bot_token"], "chatId": s["chat_id"]}


@router.put("/settings")
def put_settings(body: SettingsIn, _=Depends(require_priv)):
    with pool.connection() as conn:
        conn.execute(
            "update settings set bot_token = %s, chat_id = %s where id = 1",
            (body.botToken.strip(), body.chatId.strip()),
        )
    return {"ok": True}


@router.post("/telegram/test")
def telegram_test(_=Depends(require_priv)):
    res = telegram.send_message(telegram.test_message())
    if not res["ok"]:
        raise HTTPException(502, res["error"])
    return {"ok": True}


# ---------- attendance ----------
def _row_out(r: dict) -> dict:
    out = {"date": r["date"].isoformat(), "class_name": r["class_name"]}
    for f in ATT_FIELDS:
        out[f] = r[f]
    return out


def _scope_class(user, cls: str | None):
    if user["role"] == "teacher":
        if not user["class_name"]:
            raise HTTPException(403, "клас не призначено")
        if cls is not None and cls != user["class_name"]:
            raise HTTPException(403, "лише свій клас")
        return user["class_name"]
    return cls


@router.get("/attendance")
def att_list(request: Request, date: str | None = None, month: str | None = None):
    user = current_user(request)
    where, params = [], []
    if date:
        where.append("date = %s"); params.append(date)
    if month:
        where.append("to_char(date, 'YYYY-MM') = %s"); params.append(month)
    if user["role"] == "teacher":
        where.append("class_name = %s"); params.append(_scope_class(user, None))
    sql = "select * from attendance"
    if where:
        sql += " where " + " and ".join(where)
    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_out(r) for r in rows]


@router.get("/attendance/last/{cls}")
def att_last(cls: str, request: Request):
    """Most recent record for a class — the form prefills 'registered'/'abroad' from it."""
    _scope_class(current_user(request), cls)
    with pool.connection() as conn:
        r = conn.execute(
            "select * from attendance where class_name = %s order by date desc limit 1", (cls,)
        ).fetchone()
    return _row_out(r) if r else None


@router.get("/attendance/{date}/{cls}")
def att_get(date: str, cls: str, request: Request):
    user = current_user(request)
    _scope_class(user, cls)
    with pool.connection() as conn:
        r = conn.execute(
            "select * from attendance where date = %s and class_name = %s", (date, cls)
        ).fetchone()
    if not r:
        raise HTTPException(404, "немає запису")
    return _row_out(r)


@router.put("/attendance/{date}/{cls}")
def att_put(date: str, cls: str, body: dict, request: Request):
    user = current_user(request)
    _scope_class(user, cls)
    date_cls.fromisoformat(date)  # validate
    vals = {}
    for f in ATT_FIELDS:
        v = body.get(f)
        if f in INT_FIELDS:
            v = int(v or 0)
        elif f in NULLABLE_INT:
            v = None if v in (None, "") else int(v)
        else:
            v = (v or "").strip()
        vals[f] = v
    cols = ["date", "class_name", *ATT_FIELDS, "updated_by"]
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{f} = excluded.{f}" for f in [*ATT_FIELDS, "updated_by"]) + ", updated_at = now()"
    with pool.connection() as conn:
        conn.execute(
            f"insert into attendance ({', '.join(cols)}) values ({placeholders}) "
            f"on conflict (date, class_name) do update set {updates}",
            [date, cls, *[vals[f] for f in ATT_FIELDS], user["full_name"]],
        )
        r = conn.execute(
            "select * from attendance where date = %s and class_name = %s", (date, cls)
        ).fetchone()
    tg = telegram.send_message(telegram.attendance_message(date, cls, _row_out(r), user["full_name"]))
    return {"record": _row_out(r), "telegram": tg}


@router.delete("/attendance/{date}/{cls}")
def att_del(date: str, cls: str, request: Request):
    user = current_user(request)
    _scope_class(user, cls)
    with pool.connection() as conn:
        conn.execute("delete from attendance where date = %s and class_name = %s", (date, cls))
    return {"ok": True}


@router.post("/attendance/summary")
def att_summary(request: Request, date: str):
    user = current_user(request)
    rows = att_list(request, date=date)
    if user["role"] == "teacher":
        rows = [r for r in rows if r["class_name"] == user["class_name"]]
    if not rows:
        raise HTTPException(404, "немає даних за цю дату")
    refusals = class_refusals(request)
    for r in rows:
        r["meal_refusal"] = refusals.get(r["class_name"], 0)
    res = telegram.send_message(telegram.summary_message(date, rows))
    if not res["ok"]:
        raise HTTPException(502, res["error"])
    return {"ok": True}
