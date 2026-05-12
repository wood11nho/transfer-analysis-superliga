"""
Database helpers for the Superliga Transfer Analytics app.

This module is intentionally independent of Streamlit so it can be
reused from scripts, tests, or other environments.
"""

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from config import get_db_url

_engine: Engine | None = None


def _normalize_db_url(raw_url: str) -> str:
    """
    Normalize database URLs so they work across local and cloud runtimes.

    - Accept old-style "postgres://" and map it to SQLAlchemy's "postgresql://".
    - For non-local Postgres hosts, default to sslmode=require unless already set.
    """

    db_url = raw_url.strip()
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://") :]

    parsed = make_url(db_url)
    if parsed.get_backend_name().startswith("postgres"):
        host = (parsed.host or "").lower()
        is_local_host = host in {"", "localhost", "127.0.0.1", "::1"}
        has_sslmode = "sslmode" in parsed.query
        if not is_local_host and not has_sslmode:
            parsed = parsed.update_query_dict({"sslmode": "require"})
            db_url = parsed.render_as_string(hide_password=False)

    return db_url


def get_engine() -> Engine:
    """
    Returns a singleton SQLAlchemy engine.

    The engine is created on first use and then reused, which is
    important in a web context to avoid creating too many connections.
    """

    global _engine
    if _engine is None:
        db_url = _normalize_db_url(get_db_url())
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"connect_timeout": 10},
        )
    return _engine


def run_query(sql: str, params: dict[str, Any] | None = None):
    """
    Convenience helper to run a SQL query and return a pandas DataFrame.
    """
    import pandas as pd

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})

