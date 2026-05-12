"""
Global configuration for the Superliga Transfer Analytics app.

Database URL resolution order:
1. Environment variables (TRANSFER_DB_URL, DATABASE_URL, DB_URL).
2. Streamlit secrets under the same key names.
3. Streamlit nested secrets, e.g.:
   [database]
   url = "postgresql://..."
4. Local default Postgres URL for machine-local ETL only.
"""

import os


ENV_DB_KEYS = ("TRANSFER_DB_URL", "DATABASE_URL", "DB_URL")
SECRETS_DB_KEYS = ("TRANSFER_DB_URL", "DATABASE_URL", "DB_URL", "url")


def _first_non_empty(items: list[str | None]) -> str | None:
    for value in items:
        if value and str(value).strip():
            return str(value).strip()
    return None


def get_db_url() -> str:
    """
    Returns the database URL for the analytics app.
    """

    env_url = _first_non_empty([os.getenv(k) for k in ENV_DB_KEYS])
    if env_url:
        return env_url

    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            secrets = st.secrets

            # Top-level secrets
            top_level = _first_non_empty(
                [str(secrets[k]) if k in secrets else None for k in SECRETS_DB_KEYS]
            )
            if top_level:
                return top_level

            # Nested secrets: [database] or [db] with key url
            for section in ("database", "db"):
                if section in secrets:
                    section_value = secrets[section]
                    if isinstance(section_value, dict):
                        nested = _first_non_empty(
                            [
                                str(section_value[k]) if k in section_value else None
                                for k in ("url", "DATABASE_URL", "TRANSFER_DB_URL")
                            ]
                        )
                        if nested:
                            return nested
    except Exception:
        pass

    # Same database as local ETL; not available on Streamlit Cloud — set secrets / env above.
    return "postgresql://postgres:password@localhost:5432/romanian_football"

