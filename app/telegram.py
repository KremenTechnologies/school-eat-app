import httpx

from .db import pool

ABSENCE = [
    ("illness", "По хворобі"),
    ("grvi", "По ГРВІ"),
    ("family", "По сімейних причинах"),
    ("no_reason", "Без поважної причини"),
]
BREAKFAST_ONLY = {1, 2, 3, 4, 5, 6, 9}
LUNCH_ONLY = {7, 8}


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
            json={"chat_id": s["chat_id"], "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        data = r.json()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"мережева помилка: {e}"}
    if not data.get("ok"):
        return {"ok": False, "error": data.get("description", "помилка Telegram API")}
    return {"ok": True}


def _grade(cls: str):
    import re

    m = re.search(r"(\d{1,2})", cls or "")
    return int(m.group(1)) if m else None


def _present(rec: dict) -> int:
    absent = sum(int(rec.get(f"{k}_count") or 0) for k, _ in ABSENCE)
    p = int(rec.get("registered") or 0) - int(rec.get("abroad") or 0) - int(rec.get("individual") or 0) - absent
    return max(p, 0)


def _esc(s) -> str:
    s = "" if s is None else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attendance_message(date: str, cls: str, rec: dict, by: str) -> str:
    present = _present(rec)
    absent = sum(int(rec.get(f"{k}_count") or 0) for k, _ in ABSENCE)
    d, m, y = date.split("-")[::-1]
    lines = [
        "<b>Відвідування оновлено</b>",
        f"Дата: {d}.{m}.{y}",
        f"Клас: <b>{_esc(cls)}</b>",
        f"За реєстром: {int(rec.get('registered') or 0)}, присутні: <b>{present}</b>, відсутні: {absent}",
    ]
    for key, label in ABSENCE:
        c = int(rec.get(f"{key}_count") or 0)
        if c > 0:
            names = rec.get(f"{key}_names") or ""
            lines.append(f"— {label}: {c}" + (f" ({_esc(names)})" if names else ""))
    if by:
        lines.append(f"Внесено: {_esc(by)}")
    return "\n".join(lines)


def summary_message(date: str, records: list[dict]) -> str:
    d, m, y = date.split("-")[::-1]
    lines = [f"<b>Зведення харчування — {d}.{m}.{y}</b>", ""]
    tot_b = tot_l = 0
    for rec in sorted(records, key=lambda r: r["class_name"]):
        present = _present(rec)
        g = _grade(rec["class_name"])
        db = 0 if g in LUNCH_ONLY else present
        dl = 0 if g in BREAKFAST_ONLY else present
        b = db if rec.get("breakfast") is None else int(rec["breakfast"])
        lu = dl if rec.get("lunch") is None else int(rec["lunch"])
        tot_b += b
        tot_l += lu
        lines.append(f"{_esc(rec['class_name'])}: присутні {present}, сніданок {b}, обід {lu}")
    lines += ["", f"Разом: сніданків {tot_b}, обідів {tot_l}"]
    return "\n".join(lines)
