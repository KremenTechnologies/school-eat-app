"""Pure-function checks for Telegram message rendering (no DB, no network)."""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost/x")
os.environ.setdefault("SESSION_SECRET", "x")

from app import telegram as t  # noqa: E402

BASE = {"class_name": "5-А", "registered": 25, "abroad": 0, "individual": 0,
        "illness_count": 0, "grvi_count": 0, "family_count": 0, "no_reason_count": 0,
        "breakfast": None, "lunch": None}


def test_attendance_message_basic():
    msg = t.attendance_message("2026-09-08", "5-А", BASE, "Ін Ів")
    assert "Відвідування — 5-А" in msg
    assert "8 вересня 2026" in msg
    assert "Присутні: <b>25</b> з 25" in msg
    assert "Відсутні" not in msg  # nothing absent -> line hidden


def test_attendance_message_with_reasons():
    rec = {**BASE, "abroad": 1, "illness_count": 2, "illness_names": "А Б, В Г"}
    msg = t.attendance_message("2026-09-08", "5-А", rec, "Хтось")
    assert "Присутні: <b>22</b> з 25" in msg
    assert "🤒 Хвороба — <b>2</b>" in msg
    assert "<i>А Б, В Г</i>" in msg
    assert "за кордоном 1" in msg


def test_summary_message_meal_rules():
    recs = [
        {**BASE, "class_name": "5-А", "registered": 20},   # grade 5 -> breakfast only
        {**BASE, "class_name": "7-Б", "registered": 30},   # grade 7 -> lunch only
    ]
    msg = t.summary_message("2026-09-08", recs)
    assert "сніданків <b>20</b>, обідів <b>30</b>" in msg
    assert "<pre>" in msg and "Разом" in msg


def test_html_is_escaped():
    rec = {**BASE, "illness_count": 1, "illness_names": "<script>&"}
    assert "&lt;script&gt;&amp;" in t.attendance_message("2026-09-08", "5-А", rec, "x")


def test_grvi_not_subtracted_and_refusal_reduces_meals():
    from app.telegram import _present, _meals
    rec = {"class_name": "5-А", "registered": 20, "illness_count": 3, "grvi_count": 2, "meal_refusal": 4}
    assert _present(rec) == 17          # 20 - 3; ГРВІ is inside «по хворобі»
    assert _meals(rec) == (13, 0)       # 17 - 4 refused; grade 5 = breakfast only
