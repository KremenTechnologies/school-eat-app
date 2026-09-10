from __future__ import annotations

import re
from datetime import date as date_cls
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from .db import pool

KYIV = ZoneInfo("Europe/Kyiv")

ABSENCE = [
    ("illness", "🤒", "Хвороба"),
    ("grvi", "🤧", "ГРВІ"),
    ("family", "👨‍👩‍👧", "Сімейні причини"),
    ("no_reason", "❗", "Без поважної причини"),
]
BREAKFAST_ONLY = {1, 2, 3, 4, 5, 6, 9}
LUNCH_ONLY = {7, 8}

_MONTHS = ["", "січня", "лютого", "березня", "квітня", "травня", "червня",
          "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
_WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "нд"]


def _settings():
    with pool.connection() as conn:
        return conn.execute("select bot_token, chat_id from settings where id = 1").fetchone()


def send_message(text: str) -> dict:
    s = _settings()
    if not s or not s["bot_token"] or not s["chat_id"]:
        return {"ok": False, "error": "Telegram не налаштовано"}
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{s['bot_token']}/sendMessage",
            json={
                "chat_id": s["chat_id"],
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        data = r.json()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"мережева помилка: {e}"}
    if not data.get("ok"):
        return {"ok": False, "error": data.get("description", "помилка Telegram API")}
    return {"ok": True}


def _fmt_date(iso: str) -> str:
    d = date_cls.fromisoformat(iso)
    return f"{d.day} {_MONTHS[d.month]} {d.year} р. ({_WEEKDAYS[d.weekday()]})"


def _now_kyiv() -> str:
    return datetime.now(KYIV).strftime("%H:%M")


def _grade(cls: str):
    m = re.search(r"(\d{1,2})", cls or "")
    return int(m.group(1)) if m else None


def _present(rec: dict) -> int:
    # ГРВІ is a subgroup of illness — reported, never subtracted
    absent = sum(int(rec.get(f"{k}_count") or 0) for k, *_ in ABSENCE if k != "grvi")
    p = (int(rec.get("registered") or 0) - int(rec.get("abroad") or 0)
         - int(rec.get("individual") or 0) - absent)
    return max(p, 0)


def _meals(rec: dict) -> tuple[int, int]:
    present = max(0, _present(rec) - int(rec.get("meal_refusal") or 0))
    g = _grade(rec["class_name"])
    b_def = 0 if g in LUNCH_ONLY else present
    l_def = 0 if g in BREAKFAST_ONLY else present
    b = b_def if rec.get("breakfast") is None else int(rec["breakfast"])
    lu = l_def if rec.get("lunch") is None else int(rec["lunch"])
    return b, lu


def _esc(s) -> str:
    s = "" if s is None else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attendance_message(date: str, cls: str, rec: dict, by: str) -> str:
    reg = int(rec.get("registered") or 0)
    present = _present(rec)
    absent = sum(int(rec.get(f"{k}_count") or 0) for k, *_ in ABSENCE if k != "grvi")
    abroad = int(rec.get("abroad") or 0)
    individual = int(rec.get("individual") or 0)

    out = [
        f"📋 <b>Відвідування — {_esc(cls)}</b>",
        f"🗓 {_fmt_date(date)}",
        "",
        f"✅ Присутні: <b>{present}</b> з {reg}",
    ]
    if absent:
        out.append(f"🚫 Відсутні: <b>{absent}</b>")
    extras = []
    if abroad:
        extras.append(f"за кордоном {abroad}")
    if individual:
        extras.append(f"індив. навчання {individual}")
    if extras:
        out.append("• " + " · ".join(extras))

    reasons = []
    for key, icon, label in ABSENCE:
        c = int(rec.get(f"{key}_count") or 0)
        if not c:
            continue
        names = (rec.get(f"{key}_names") or "").strip()
        line = f"{icon} {label} — <b>{c}</b>"
        if names:
            line += f"\n   <i>{_esc(names)}</i>"
        reasons.append(line)
    if reasons:
        out += ["", *reasons]

    out += ["", f"✏️ {_esc(by)} · {_now_kyiv()}"] if by else ["", f"✏️ {_now_kyiv()}"]
    return "\n".join(out)


def summary_message(date: str, records: list[dict]) -> str:
    rows = sorted(records, key=lambda r: r["class_name"])
    tot_p = tot_b = tot_l = 0
    table = [f"{'Клас':<8}{'Присут.':>8}{'Снід.':>7}{'Обід':>7}"]
    for rec in rows:
        present = _present(rec)
        b, lu = _meals(rec)
        tot_p += present
        tot_b += b
        tot_l += lu
        table.append(
            f"{rec['class_name']:<8}{present:>8}{(b or '–'):>7}{(lu or '–'):>7}"
        )
    table.append("─" * 30)
    table.append(f"{'Разом':<8}{tot_p:>8}{tot_b:>7}{tot_l:>7}")

    return (
        f"🍽 <b>Заявки на харчування</b>\n"
        f"🗓 {_fmt_date(date)}\n"
        f"Класів з даними: {len(rows)}\n\n"
        f"<pre>{_esc(chr(10).join(table))}</pre>\n"
        f"Разом порцій: сніданків <b>{tot_b}</b>, обідів <b>{tot_l}</b>\n"
        f"<i>Надіслано {_now_kyiv()}</i>"
    )


def test_message() -> str:
    return (
        "✅ <b>Telegram підключено</b>\n"
        "Сюди надходитимуть сповіщення про відвідування та заявки на харчування.\n"
        f"<i>Перевірка {_now_kyiv()}</i>"
    )
