"""
General Insights page: exact notebook visualizations from data_analysis.ipynb.

Each chart is rendered in the same format and style as in the notebook.
"""

import streamlit as st
import matplotlib.pyplot as plt

from notebook_viz import (
    prepare_data,
    viz1_position_spend,
    viz2_free_agents_by_position,
    viz3_free_vs_paid_over_time,
    viz4_origins_by_region,
    viz5_age_paid_vs_free,
    viz6_transfer_corridors,
)


@st.cache_data(show_spinner="Loading notebook data…")
def load_bundle():
    """Load and prepare all data used by the notebook visualizations."""
    return prepare_data()


def main():
    st.set_page_config(page_title="General Insights | Superliga", layout="wide", page_icon="📊")
    st.title("📊 General Insights")
    bundle = load_bundle()
    if bundle["df"].empty:
        st.error("No data found. Ensure a combined file like `data/romania_transfers_combined_*.csv` exists.")
        return

    season_min = bundle.get("season_min")
    season_max = bundle.get("season_max")
    if season_min is not None and season_max is not None:
        st.caption(
            "Same analyses and charts as in the exploratory notebook (data_analysis.ipynb). "
            f"Data: Romanian League transfers {season_min}-{season_max} from Transfermarkt."
        )
    else:
        st.caption(
            "Same analyses and charts as in the exploratory notebook (data_analysis.ipynb). "
            "Data: Romanian League transfers from Transfermarkt."
        )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Viz 1 – Position spend %",
        "Viz 2 – Free agents by position",
        "Viz 3 – Free vs paid over time",
        "Viz 4 – Origins by region",
        "Viz 5 – Age: paid vs free",
        "Viz 6 – Transfer corridors",
    ])

    with tab1:
        if season_min is not None and season_max is not None:
            st.subheader(f"Percentage of Money Spent by Position ({season_min}-{season_max})")
        else:
            st.subheader("Percentage of Money Spent by Position")
        fig = viz1_position_spend(bundle)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with tab2:
        st.subheader("Number of Free Agent Signings by Position")
        fig = viz2_free_agents_by_position(bundle)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with tab3:
        st.subheader("Free vs Paid Transfers Over Time")
        fig = viz3_free_vs_paid_over_time(bundle)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with tab4:
        st.subheader("Player Origins by Region Over Time")
        fig = viz4_origins_by_region(bundle)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with tab5:
        st.subheader("Age Distribution: Paid vs Free Transfers")
        fig = viz5_age_paid_vs_free(bundle)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with tab6:
        st.subheader("Transfer Corridors & Scouting Networks")
        fig = viz6_transfer_corridors(bundle)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)


if __name__ == "__main__":
    main()
