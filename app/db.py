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
