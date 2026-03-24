import streamlit as st

from db import get_engine
from queries import load_competition_base_df


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

    init_app()
    show_home()


if __name__ == "__main__":
    main()

