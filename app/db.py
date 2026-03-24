"""
Database helpers for the Superliga Transfer Analytics app.

This module is intentionally independent of Streamlit so it can be
reused from scripts, tests, or other environments.
"""

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config import get_db_url

_engine: Engine | None = None


def get_engine() -> Engine:
    """
    Returns a singleton SQLAlchemy engine.

    The engine is created on first use and then reused, which is
    important in a web context to avoid creating too many connections.
    """

    global _engine
    if _engine is None:
        _engine = create_engine(get_db_url())
    return _engine


def run_query(sql: str, params: dict[str, Any] | None = None):
    """
    Convenience helper to run a SQL query and return a pandas DataFrame.
    """
    import pandas as pd

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})

