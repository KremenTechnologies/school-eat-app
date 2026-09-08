import os
import re
from pathlib import Path

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

_SCHEMA = (Path(__file__).parent.parent / "schema.sql").read_text(encoding="utf-8")

_dsn = os.environ["DATABASE_URL"]
# render gives postg:// ; psycopg wants postgresql://
_dsn = re.sub(r"^postgres://", "postgresql://", _dsn)

pool = ConnectionPool(_dsn, min_size=1, max_size=10, open=False, kwargs={"row_factory": dict_row})


def canon_phone(phone: str) -> str:
    """Canonical phone: last 9 canon_phone (UA subscriber number).

    '+380 67 707 40 27', '380677074027' and '067 707 40 27' all -> '677074027'.
    """
    d = re.sub(r"\D", "", phone or "")
    return d[-9:] if len(d) >= 9 else d


def init_schema() -> None:
    with pool.connection() as conn:
        conn.execute(_SCHEMA)


SEED_CLASSES = [
    "1-А", "1-Б", "1-В",
    "2-А", "2-Б", "2-В",
    "3-А", "3-Б", "3-В", "3-Г",
    "4-А", "4-Б", "4-В",
    "5-А", "5-Б", "5-В",
    "6-А", "6-Б", "6-В",
    "7-А", "7-Б", "7-В",
    "8-А", "8-Б", "8-В",
    "9-А", "9-Б", "9-В",
]


def seed_classes() -> None:
    with pool.connection() as conn:
        for name in SEED_CLASSES:
            conn.execute("insert into classes (name) values (%s) on conflict do nothing", (name,))


def seed_developers() -> None:
    devs = [
        (os.environ.get("DEV1_PHONE"), os.environ.get("DEV1_NAME")),
        (os.environ.get("DEV2_PHONE"), os.environ.get("DEV2_NAME")),
    ]
    with pool.connection() as conn:
        for phone, name in devs:
            if not phone or not name:
                continue
            conn.execute(
                "insert into users (phone, full_name, role) values (%s, %s, 'developer') "
                "on conflict (phone) do nothing",
                (canon_phone(phone), name.strip()),
            )
