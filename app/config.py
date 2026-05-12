"""
Global configuration for the Superliga Transfer Analytics app.

Database URL resolution order:
1. Environment variable ``TRANSFER_DB_URL`` (local dev, Docker, CI).
2. Streamlit secrets ``TRANSFER_DB_URL`` (Streamlit Community Cloud reads the
   dashboard “Secrets” TOML into ``st.secrets``, not into ``os.environ``).
3. Local default Postgres URL for the ETL pipeline on your machine only.
"""

import os


def get_db_url() -> str:
    """
    Returns the database URL for the analytics app.
    """

    env_url = os.getenv("TRANSFER_DB_URL")
    if env_url:
        return env_url.strip()

    try:
        import streamlit as st

        if hasattr(st, "secrets") and "TRANSFER_DB_URL" in st.secrets:
            return str(st.secrets["TRANSFER_DB_URL"]).strip()
    except Exception:
        pass

    # Same database as local ETL; not available on Streamlit Cloud — set secrets / env above.
    return "postgresql://postgres:password@localhost:5432/romanian_football"

