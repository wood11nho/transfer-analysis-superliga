import streamlit as st
from sqlalchemy.exc import OperationalError

from db import get_engine
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
        Explore two decades of Romanian Superliga transfers — fees, free
        agents, age and position trends, nationality flows, and how
        Romanian clubs trade against the rest of European football.
        """
    )

    st.markdown(
        """
        ### Where to start

        Open a page from the **menu on the left**:

        - **Competition** — season-by-season analysis with financials,
          age profile, origin & nationality, positions, deal structure,
          European impact, and a searchable register of every transfer.
        - **General Insights** — high-level visual stories: spending by
          position, free vs. paid market, scouting corridors, and more.
        """
    )

    st.info(
        "Tip: use the **Filters** in the sidebar of each page to narrow the "
        "view by season, club, position, nationality, age, or deal type.",
        icon="💡",
    )


def main():
    st.set_page_config(
        page_title="Superliga Transfer Analytics",
        layout="wide",
        page_icon="🏆",
    )

    try:
        init_app()
    except OperationalError as exc:
        st.error("The analytics database is currently unreachable.")
        st.markdown(
            "Please try refreshing in a few moments. If the issue persists, "
            "you can let the team know through the **Feedback** form in the sidebar."
        )
        with st.expander("Technical details (for administrators)"):
            st.markdown(
                "Configure the database connection by setting `DATABASE_URL` "
                "(or `TRANSFER_DB_URL`) in the deployment's environment or "
                "Streamlit secrets, for example:\n\n"
                "```\n"
                "DATABASE_URL = \"postgresql://user:password@host:5432/dbname?sslmode=require\"\n"
                "```"
            )
            st.caption(f"Driver error: {exc}")
        st.stop()

    show_home()
    render_page_chrome(page_title="Home")


if __name__ == "__main__":
    main()

