import streamlit as st
from sqlalchemy.exc import OperationalError

from db import get_engine
from queries import load_competition_base_df
from ui import render_page_chrome


def init_app():
    """
    Run one-time initialization logic.

    For now we simply ensure the database is reachable. In a larger
    project you might also warm caches, load metadata, etc.
    """
    # Touch the engine once so that connection errors fail fast
    _ = get_engine()


def show_home():
    st.title("🏆 Superliga Transfer Analytics")
    st.write(
        """
        This application explores Romanian Superliga transfers using the
        cleaned warehouse schema you built (`dim_players`, `dim_clubs`,
        `fact_transfers`).
        """
    )

    st.markdown(
        """
        ### Navigation

        Use the **Pages** menu (on the left) to access:

        - **Competition** — league/season level analysis with financials,
          age, nationality, origin, positions, and more.
        - Additional pages (Players, Clubs, etc.) can be added later.
        """
    )

    with st.expander("Quick sanity check (sample data)"):
        df = load_competition_base_df(seasons=None)
        st.write(df.head())


def main():
    st.set_page_config(
        page_title="Superliga Transfer Analytics",
        layout="wide",
        page_icon="🏆",
    )

    try:
        init_app()
    except OperationalError as exc:
        st.error("Database connection failed.")
        st.markdown(
            """
            ### How to fix this on Streamlit Cloud

            1. Add one of these keys in app **Settings -> Secrets**:
               `TRANSFER_DB_URL` or `DATABASE_URL`.
            2. Use a remote Postgres URL (not localhost).
            3. Ensure your database allows external connections.

            Example:

            `DATABASE_URL = "postgresql://user:password@host:5432/dbname?sslmode=require"`
            """
        )
        st.info(
            "If no secret/env DB URL is found, the app intentionally falls back "
            "to localhost for local development only."
        )
        st.caption(f"SQLAlchemy error: {exc}")
        st.stop()

    show_home()
    render_page_chrome(page_title="Home")


if __name__ == "__main__":
    main()

