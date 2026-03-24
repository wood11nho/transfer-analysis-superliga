"""
Global configuration for the Superliga Transfer Analytics app.

In a production setup you would typically read the database URL and
other secrets from environment variables or a secrets manager.
For now we centralize the Postgres connection string here so that
all modules use a single source of truth.
"""

import os


def get_db_url() -> str:
    """
    Returns the database URL for the analytics app.

    Priority:
    1. ENV VAR: TRANSFER_DB_URL
    2. Fallback: local Postgres instance used elsewhere in the project
    """

    env_url = os.getenv("TRANSFER_DB_URL")
    if env_url:
        return env_url

    # Fallback to the same database used by the ETL pipeline
    return "postgresql://postgres:password@localhost:5432/romanian_football"

