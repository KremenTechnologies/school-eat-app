"""Smoke test for the REST API. Needs a throwaway Postgres in DATABASE_URL.

    DATABASE_URL=postgresql://localhost/school_eat_test SMS_DEBUG=1 uv run pytest
"""
import os

import pytest

os.environ.setdefault("SESSION_SECRET", "test")
os.environ.setdefault("SMS_DEBUG", "1")
# the fixture seeds its own developer; ignore any real DEV* from .env
os.environ["DEV1_PHONE"] = "+380670000001"
os.environ["DEV1_NAME"] = "Тест Розробник"
os.environ.pop("DEV2_PHONE", None)
os.environ.pop("DEV2_NAME", None)

_test_db = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not _test_db:
    pytest.skip("set TEST_DATABASE_URL (or DATABASE_URL) to a throwaway Postgres", allow_module_level=True)
os.environ["DATABASE_URL"] = _test_db  # the fixture drops & recreates every table here

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    db.pool.open()
    with db.pool.connection() as conn:
        conn.execute("drop table if exists users, classes, settings, attendance, login_codes cascade")
    db.init_schema()
    db.seed_developers()
    with TestClient(app) as c:
        yield c


def login_dev(c):
    r = c.post("/api/login", json={"phone": "+38 (067) 000-00-01", "name": "  тест   розробник "})
    assert r.status_code == 200, r.text
    return r.json()


def test_seed_and_name_login(client):
    me = login_dev(client)
    assert me["role"] == "developer"
    assert client.get("/api/me").json()["name"] == "Тест Розробник"


def test_sms_login(client):
    assert client.post("/api/login/sms/request", json={"phone": "380670000001"}).status_code == 200
    # second request within the 5-min window is rejected
    assert client.post("/api/login/sms/request", json={"phone": "380670000001"}).status_code == 429
    with db.pool.connection() as conn:
        code = conn.execute("select code from login_codes").fetchone()["code"]
    assert client.post("/api/login/sms/verify",
                       json={"phone": "380670000001", "code": "000000"}).status_code == 400
    r = client.post("/api/login/sms/verify", json={"phone": "380670000001", "code": code})
    assert r.status_code == 200 and r.json()["role"] == "developer"


def test_classes_and_attendance_flow(client):
    login_dev(client)
    seeded = client.get("/api/classes").json()
    assert "5-А" in seeded and "9-В" in seeded  # seed_classes ran on startup
    client.post("/api/classes", json=[{"name": "11-Я"}])
    assert "11-Я" in client.get("/api/classes").json()

    rec = {"registered": 25, "abroad": 1, "individual": 0,
           "illness_count": 2, "illness_names": "Іваненко Іван, Петренко Петро"}
    r = client.put("/api/attendance/2026-09-08/5-А", json=rec)
    assert r.status_code == 200
    got = client.get("/api/attendance/2026-09-08/5-А").json()
    assert got["registered"] == 25 and got["illness_count"] == 2

    assert len(client.get("/api/attendance?date=2026-09-08").json()) == 1
    assert len(client.get("/api/attendance?month=2026-09").json()) == 1

    client.delete("/api/attendance/2026-09-08/5-А")
    assert client.get("/api/attendance?date=2026-09-08").json() == []


def test_teacher_is_scoped_to_own_class(client):
    login_dev(client)
    client.post("/api/classes", json=[{"name": "5-А"}, {"name": "7-Б"}])
    client.post("/api/users", json={"name": "Вчителька Одна", "phone": "0671111111",
                                    "role": "teacher", "className": "5-А"})
    client.put("/api/attendance/2026-09-08/5-А", json={"registered": 20})
    client.put("/api/attendance/2026-09-08/7-Б", json={"registered": 30})
    client.post("/api/logout")

    t = TestClient(app)
    assert t.post("/api/login", json={"phone": "0671111111", "name": "одна вчителька"}).status_code == 200
    assert [r["class_name"] for r in t.get("/api/attendance?date=2026-09-08").json()] == ["5-А"]
    assert t.put("/api/attendance/2026-09-08/7-Б", json={"registered": 1}).status_code == 403


def test_admin_cannot_be_created_by_admin(client):
    login_dev(client)
    client.post("/api/users", json={"name": "Адмін Один", "phone": "0672222222", "role": "admin"})
    client.post("/api/logout")

    a = TestClient(app)
    a.post("/api/login", json={"phone": "0672222222", "name": "ОДИН адмін"})
    r = a.post("/api/users", json={"name": "Адмін Два", "phone": "0673333333", "role": "admin"})
    assert r.status_code == 403


def test_refusal_and_last_record(client):
    login_dev(client)
    assert client.get("/api/attendance/last/5-А").json() is None
    client.put("/api/attendance/2026-09-01/5-А", json={"registered": 20, "abroad": 2})
    client.put("/api/attendance/2026-09-08/5-А", json={"registered": 25, "abroad": 1})
    last = client.get("/api/attendance/last/5-А").json()
    assert (last["registered"], last["abroad"]) == (25, 1)

    assert client.get("/api/classes/refusals").json()["5-А"] == 0
    assert client.put("/api/classes/5-А/refusal", json={"meal_refusal": 3}).json() == {"meal_refusal": 3}
    assert client.get("/api/classes/refusals").json()["5-А"] == 3
