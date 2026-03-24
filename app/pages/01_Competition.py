import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from queries import load_competition_base_df
from uefa_coefficients import (
    UEFA_CSV_PATH,
    attach_counterparty_ranks,
    is_romania_counterparty_country,
    load_uefa_long,
    romania_rank_series,
)


@st.cache_data(show_spinner=True)
def load_data(selected_seasons: list[str] | None):
    return load_competition_base_df(selected_seasons)


def build_filters(df: pd.DataFrame):
    st.sidebar.header("Filters")

    seasons = sorted(df["season"].dropna().unique().tolist())
    selected_seasons = st.sidebar.multiselect(
        "Season(s)", seasons
    )

    leagues = sorted(
        pd.Series(
            [v for v in df.get("team1_country", pd.Series()).dropna().unique().tolist()]
        )
    )

    clubs = sorted(
        pd.Series(
            [v for v in df.get("team1", pd.Series()).dropna().unique().tolist()]
        )
    )

    positions = sorted(df["player_position"].dropna().unique().tolist())
    nationalities = sorted(df["player_nationality"].dropna().unique().tolist())

    age_min = int(df["player_age"].min()) if df["player_age"].notna().any() else 15
    age_max = int(df["player_age"].max()) if df["player_age"].notna().any() else 40

    selected_clubs = st.sidebar.multiselect("Team 1 (Perspective Team)", clubs)
    selected_positions = st.sidebar.multiselect("Position(s)", positions)
    selected_nationalities = st.sidebar.multiselect("Nationality(ies)", nationalities)
    age_range = st.sidebar.slider(
        "Age range",
        min_value=age_min,
        max_value=age_max,
        value=(age_min, age_max),
    )

    free_opts = st.sidebar.multiselect(
        "Deal type",
        options=["Paid", "Loan", "Free"],
        default=["Paid", "Loan", "Free"],
        help="Paid: fee > 0, Loan: is_loan = True, Free: fee = 0 and not loan",
    )

    return {
        "seasons": selected_seasons,
        "clubs": selected_clubs,
        "positions": selected_positions,
        "nationalities": selected_nationalities,
        "age_range": age_range,
        "deal_types": free_opts,
    }


def apply_filters(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    out = df.copy()

    if f["seasons"]:
        out = out[out["season"].isin(f["seasons"])]

    if f["clubs"]:
        out = out[out["team1"].isin(f["clubs"])]

    if f["positions"]:
        out = out[out["player_position"].isin(f["positions"])]

    if f["nationalities"]:
        out = out[out["player_nationality"].isin(f["nationalities"])]

    age_min, age_max = f["age_range"]
    out = out[
        (out["player_age"].isna())
        | ((out["player_age"] >= age_min) & (out["player_age"] <= age_max))
    ]

    # Deal type (Paid / Loan / Free)
    if f["deal_types"]:
        paid_mask = (out["transfer_fee_amount"] > 0) & (~out["is_loan"])
        loan_mask = out["is_loan"]
        free_mask = (out["transfer_fee_amount"] == 0) & (~out["is_loan"])

        mask = pd.Series(False, index=out.index)
        if "Paid" in f["deal_types"]:
            mask |= paid_mask
        if "Loan" in f["deal_types"]:
            mask |= loan_mask
        if "Free" in f["deal_types"]:
            mask |= free_mask
        out = out[mask]

    return out


def kpi_section(df: pd.DataFrame):
    total_transfers = len(df)
    total_players = df["player_id"].nunique()
    total_expenses = df["expense"].sum()
    total_income = df["income"].sum()
    net_balance = total_income - total_expenses
    avg_age = df["player_age"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Transfers", f"{total_transfers:,}")
    c2.metric("Unique players", f"{total_players:,}")
    c3.metric("Expenses (€)", f"{total_expenses:,.0f}")
    c4.metric("Income (€)", f"{total_income:,.0f}")
    c5.metric(
        "Net balance (€)",
        f"{net_balance:,.0f}",
        delta=None,
    )

    st.caption(
        "From each club's perspective: paid arrivals are counted as expenses, "
        "paid departures as income. Loans and free transfers are tracked separately."
    )


def enrich_deal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive financial and deal-type columns:
    - expense / income from Team 1 perspective
    - deal_type: Paid / Loan / Free
    """
    out = df.copy()

    # Deal type
    paid_mask = (out["transfer_fee_amount"] > 0) & (~out["is_loan"])
    loan_mask = out["is_loan"]
    free_mask = (out["transfer_fee_amount"] == 0) & (~out["is_loan"])

    out["deal_type"] = np.select(
        [paid_mask, loan_mask, free_mask],
        ["Paid", "Loan", "Free"],
        default="Other",
    )

    # Financials from Team 1 perspective
    out["expense"] = 0.0
    out["income"] = 0.0

    arrivals = out["transfer_type_code"] == 1  # Arrivals: team2 -> team1
    departures = out["transfer_type_code"] == 2  # Departures: team1 -> team2

    out.loc[arrivals & paid_mask, "expense"] = out["transfer_fee_amount"]
    out.loc[departures & paid_mask, "income"] = out["transfer_fee_amount"]

    return out


def financials_section(df: pd.DataFrame):
    st.subheader("Financials: expenses vs. income")
    st.write(
        "This view explains how clubs spend and earn in the transfer market. "
        "Use it to compare season trends, identify efficient clubs, and inspect "
        "full club-level breakdowns."
    )

    if df.empty:
        st.info("No data for financial analysis with the current filters.")
        return

    st.markdown(
        """
        **How to read these numbers**
        - **Expenses**: transfer fees paid for incoming players  
        - **Income**: transfer fees received for outgoing players  
        - **Net balance**: income minus expenses  
        """
    )

    # By season
    by_season = (
        df.groupby("season")[["expense", "income"]]
        .sum()
        .reset_index()
        .sort_values("season")
    )
    by_season["net_balance"] = by_season["income"] - by_season["expense"]

    fig_season = px.bar(
        by_season,
        x="season",
        y=["expense", "income"],
        barmode="group",
        title="Expenses vs. income by season (Team 1 perspective)",
        labels={"value": "Amount (€)", "variable": "Type"},
    )
    st.plotly_chart(fig_season, use_container_width=True)

    fig_season_net = px.line(
        by_season,
        x="season",
        y="net_balance",
        markers=True,
        title="Net transfer balance by season",
        labels={"net_balance": "Net balance (€)"},
    )
    st.plotly_chart(fig_season_net, use_container_width=True)

    # By club (Team 1)
    st.markdown("#### Top 20 clubs by net transfer balance")
    by_club_all = (
        df.groupby("team1")[["expense", "income"]]
        .sum()
        .reset_index()
        .rename(columns={"team1": "club"})
    )
    if not by_club_all.empty:
        by_club_all["net"] = by_club_all["income"] - by_club_all["expense"]
        by_club_top20 = by_club_all.sort_values("net", ascending=False).head(20)

        fig_club = px.bar(
            by_club_top20,
            x="club",
            y="net",
            title="Net transfer balance by club (top 20)",
            labels={"net": "Net balance (€)"},
        )
        fig_club.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_club, use_container_width=True)

        # Extra high-signal ranking views
        col_best, col_worst = st.columns(2)
        with col_best:
            best_10 = by_club_all.sort_values("net", ascending=False).head(10)
            fig_best = px.bar(
                best_10,
                x="club",
                y="net",
                title="Best net sellers (top 10)",
                labels={"net": "Net balance (€)"},
            )
            fig_best.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_best, use_container_width=True)
        with col_worst:
            worst_10 = by_club_all.sort_values("net", ascending=True).head(10)
            fig_worst = px.bar(
                worst_10,
                x="club",
                y="net",
                title="Biggest net spenders (top 10)",
                labels={"net": "Net balance (€)"},
            )
            fig_worst.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_worst, use_container_width=True)

        st.markdown("#### Detailed club financial report (all teams)")
        report = by_club_all.copy()
        report["total_activity"] = report["income"] + report["expense"]
        
        # Calculate as percentages that always sum to 100%
        report["income_share"] = np.where(
            report["total_activity"] > 0,
            100 * report["income"] / (report["income"] + report["expense"]),
            0.0,
        )
        report["expense_share"] = np.where(
            report["total_activity"] > 0,
            100 * report["expense"] / (report["income"] + report["expense"]),
            0.0,
        )
        report["efficiency_ratio"] = np.where(
            report["expense"] > 0,
            report["income"] / report["expense"],
            np.nan,
        )

        report = report.sort_values("net", ascending=False)
        report_display = report.rename(
            columns={
                "club": "Club",
                "income": "Income (€)",
                "expense": "Expenses (€)",
                "net": "Net balance (€)",
                "total_activity": "Total activity (€)",
                "income_share": "Income share",
                "expense_share": "Expense share",
                "efficiency_ratio": "Income/Expense ratio",
            }
        )

        # Ensure financial columns are actual numbers
        for col in [
            "Income (€)",
            "Expenses (€)",
            "Net balance (€)",
            "Total activity (€)",
            "Income/Expense ratio",
        ]:
            report_display[col] = pd.to_numeric(report_display[col], errors="coerce")
            
        for col in ["Income share", "Expense share"]:
            report_display[col] = pd.to_numeric(report_display[col], errors="coerce")

        # Display using the native numeric columns with "localized" formatting
        st.dataframe(
            report_display[
                [
                    "Club",
                    "Income (€)",
                    "Expenses (€)",
                    "Net balance (€)",
                    "Total activity (€)",
                    "Income share",
                    "Expense share",
                    "Income/Expense ratio",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Income (€)": st.column_config.NumberColumn(
                    format="localized", help="Total incoming transfers (€)"
                ),
                "Expenses (€)": st.column_config.NumberColumn(
                    format="localized", help="Total outgoing transfers (€)"
                ),
                "Net balance (€)": st.column_config.NumberColumn(
                    format="localized", help="Income minus Expenses (€)"
                ),
                "Total activity (€)": st.column_config.NumberColumn(
                    format="localized", help="Sum of Income and Expenses (€)"
                ),
                "Income share": st.column_config.ProgressColumn(
                    min_value=0, max_value=100, format="%.1f%%"
                ),
                "Expense share": st.column_config.ProgressColumn(
                    min_value=0, max_value=100, format="%.1f%%"
                ),
                "Income/Expense ratio": st.column_config.NumberColumn(
                    format="localized", help="Income divided by Expenses"
                ),
            },
        )

        # Exporting raw numbers to CSV is usually better for users opening it in Excel
        csv_data = report_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download detailed club report as CSV",
            data=csv_data,
            file_name="club_financial_report.csv",
            mime="text/csv",
        )
    else:
        st.info("No club-level financial data for the current filters.")


def age_section(df: pd.DataFrame):
    st.subheader("Age profile and recruitment strategy")
    st.write(
        "This section shows the age strategy behind transfer activity: "
        "who clubs bring in, who they let go, and how this changes over time."
    )

    age_data = df.copy()
    age_data["player_age"] = pd.to_numeric(age_data["player_age"], errors="coerce")
    age_data = age_data[age_data["player_age"].notna()].copy()

    if age_data.empty:
        st.info("No age data available for the current filters.")
        return

    age_data["transfer_side"] = np.where(
        age_data["transfer_type_code"] == 1,
        "Arrivals",
        np.where(age_data["transfer_type_code"] == 2, "Departures", "Other"),
    )
    age_data = age_data[age_data["transfer_side"].isin(["Arrivals", "Departures"])].copy()

    if age_data.empty:
        st.info("No arrivals/departures age data available for the current filters.")
        return

    arrivals = age_data[age_data["transfer_side"] == "Arrivals"]
    departures = age_data[age_data["transfer_side"] == "Departures"]

    avg_all = age_data["player_age"].mean()
    avg_arr = arrivals["player_age"].mean() if not arrivals.empty else np.nan
    avg_dep = departures["player_age"].mean() if not departures.empty else np.nan
    med_arr = arrivals["player_age"].median() if not arrivals.empty else np.nan
    med_dep = departures["player_age"].median() if not departures.empty else np.nan
    u23_share_arr = (
        (arrivals["player_age"] <= 23).mean() * 100 if not arrivals.empty else np.nan
    )
    u23_share_dep = (
        (departures["player_age"] <= 23).mean() * 100 if not departures.empty else np.nan
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Average age (all transfers)", f"{avg_all:.1f}")
    m2.metric(
        "Average age (arrivals)",
        f"{avg_arr:.1f}" if pd.notna(avg_arr) else "N/A",
        delta=(
            f"{(avg_arr - avg_dep):+.1f} vs departures"
            if pd.notna(avg_arr) and pd.notna(avg_dep)
            else None
        ),
    )
    m3.metric(
        "Average age (departures)",
        f"{avg_dep:.1f}" if pd.notna(avg_dep) else "N/A",
    )
    m4.metric(
        "Under-23 share",
        (
            f"Arr {u23_share_arr:.1f}% | Dep {u23_share_dep:.1f}%"
            if pd.notna(u23_share_arr) and pd.notna(u23_share_dep)
            else "N/A"
        ),
    )

    st.caption(
        "Tip: if arrivals are younger than departures, clubs are generally rejuvenating squads."
    )

    c1, c2 = st.columns(2)

    with c1:
        fig_dist = px.histogram(
            age_data,
            x="player_age",
            color="transfer_side",
            barmode="overlay",
            opacity=0.65,
            nbins=24,
            title="Age distribution: arrivals vs departures",
            labels={"player_age": "Age", "transfer_side": "Transfer side"},
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
        )
        
        # Add bargap here! Values between 0.1 and 0.3 usually look best.
        fig_dist.update_layout(
            template="plotly_white", 
            bargap=0.2 
        )
        
        st.plotly_chart(fig_dist, use_container_width=True)

    with c2:
        fig_box = px.box(
            age_data,
            x="transfer_side",
            y="player_age",
            color="transfer_side",
            points="outliers",
            title="Age spread and outliers by transfer side",
            labels={"player_age": "Age", "transfer_side": "Transfer side"},
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
        )
        fig_box.update_layout(template="plotly_white", showlegend=False)
        st.plotly_chart(fig_box, use_container_width=True)

    trend = (
        age_data.groupby(["season", "transfer_side"])["player_age"]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(columns={"mean": "avg_age", "median": "median_age", "count": "transfers"})
        .sort_values("season")
    )

    c3, c4 = st.columns(2)
    with c3:
        fig_trend_avg = px.line(
            trend,
            x="season",
            y="avg_age",
            color="transfer_side",
            markers=True,
            title="Average age over time",
            labels={"avg_age": "Average age", "transfer_side": "Transfer side"},
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
        )
        fig_trend_avg.update_layout(template="plotly_white")
        st.plotly_chart(fig_trend_avg, use_container_width=True)

    with c4:
        fig_trend_count = px.bar(
            trend,
            x="season",
            y="transfers",
            color="transfer_side",
            barmode="group",
            title="Transfer volume: arrivals vs departures by season",
            labels={"transfers": "Number of transfers", "transfer_side": "Transfer side"},
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
        )
        fig_trend_count.update_layout(template="plotly_white")
        st.plotly_chart(fig_trend_count, use_container_width=True)

    st.markdown("#### Club-level age strategy")

    club_age = (
        age_data.groupby(["team1", "transfer_side"])["player_age"]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(columns={"team1": "club", "mean": "avg_age", "median": "median_age", "count": "transfers"})
    )
    club_age = club_age[club_age["transfers"] >= 5].copy()

    if club_age.empty:
        st.info("Not enough club-level age data for the current filters.")
        return

    top_club_volume = (
        club_age.groupby("club")["transfers"].sum().reset_index().sort_values("transfers", ascending=False).head(15)
    )
    club_age_top = club_age[club_age["club"].isin(top_club_volume["club"])]

    fig_club = px.scatter(
        club_age_top,
        x="avg_age",
        y="club",
        size="transfers",
        color="transfer_side",
        hover_data={"median_age": ":.1f", "transfers": True},
        title="Top clubs: average age by transfer side (bubble size = transfer volume)",
        labels={"avg_age": "Average age", "club": "Club", "transfer_side": "Transfer side"},
        color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
    )
    fig_club.update_layout(template="plotly_white")
    st.plotly_chart(fig_club, use_container_width=True)

    club_arr = club_age[club_age["transfer_side"] == "Arrivals"][["club", "avg_age", "median_age", "transfers"]].rename(
        columns={"avg_age": "Arrivals avg age", "median_age": "Arrivals median age", "transfers": "Arrivals transfers"}
    )
    club_dep = club_age[club_age["transfer_side"] == "Departures"][["club", "avg_age", "median_age", "transfers"]].rename(
        columns={"avg_age": "Departures avg age", "median_age": "Departures median age", "transfers": "Departures transfers"}
    )
    club_report = club_arr.merge(club_dep, on="club", how="outer")
    club_report["Age gap (Arrivals - Departures)"] = (
        club_report["Arrivals avg age"] - club_report["Departures avg age"]
    )
    club_report = club_report.sort_values("Age gap (Arrivals - Departures)", ascending=True)

    st.markdown("#### Detailed club age report (arrivals vs departures)")
    st.dataframe(
        club_report,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Arrivals avg age": st.column_config.NumberColumn(format="%.1f"),
            "Arrivals median age": st.column_config.NumberColumn(format="%.1f"),
            "Departures avg age": st.column_config.NumberColumn(format="%.1f"),
            "Departures median age": st.column_config.NumberColumn(format="%.1f"),
            "Age gap (Arrivals - Departures)": st.column_config.NumberColumn(format="%.1f"),
        },
    )


def _origin_transfer_side(df: pd.DataFrame) -> pd.DataFrame:
    """Arrivals / Departures only; respects sidebar filters already applied."""
    out = df.copy()
    out["transfer_side"] = np.where(
        out["transfer_type_code"] == 1,
        "Arrivals",
        np.where(out["transfer_type_code"] == 2, "Departures", "Other"),
    )
    out = out[out["transfer_side"].isin(["Arrivals", "Departures"])].copy()
    out["player_nationality"] = out["player_nationality"].fillna("(Unknown)").replace("", "(Unknown)")
    if "team2_country" in out.columns:
        out["other_club_country"] = out["team2_country"].fillna("(Unknown)").replace("", "(Unknown)")
    else:
        out["other_club_country"] = "(Unknown)"
    return out


def _ranked_bar_h(counts_df: pd.DataFrame, x_col: str, y_col: str, title: str, color: str):
    if counts_df.empty:
        return None
    fig = px.bar(
        counts_df.iloc[::-1],
        x=y_col,
        y=x_col,
        orientation="h",
        title=title,
        labels={y_col: "Transfers", x_col: ""},
        color_discrete_sequence=[color],
    )
    fig.update_layout(template="plotly_white", showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def origin_nationality_section(df: pd.DataFrame):
    st.subheader("Origin & nationality")
    st.write(
        "See where players come from **as people** (passport / nationality) and **as market links** "
        "(country of the other club in the deal). **Arrivals** and **Departures** are shown separately — "
        "they answer different questions: who you sign vs who you sell or release."
    )

    work = _origin_transfer_side(df)
    if work.empty:
        st.info("No arrivals or departures match the current filters.")
        return

    exclude_ro_nat = st.checkbox(
        "Hide **Romania** in nationality ranking charts",
        value=True,
        help="Romanian players often dominate locally; hiding Romania makes it easier to compare other countries.",
    )
    exclude_ro_country = st.checkbox(
        "Hide **Romania** in “other club country” ranking charts",
        value=True,
        help="Many moves involve Romanian clubs on both sides; hiding Romania highlights foreign league links.",
    )

    arrivals = work[work["transfer_side"] == "Arrivals"]
    departures = work[work["transfer_side"] == "Departures"]

    def nat_frame(side_df: pd.DataFrame, exclude_ro: bool) -> pd.DataFrame:
        d = side_df.copy()
        if exclude_ro:
            d = d[d["player_nationality"] != "Romania"]
        vc = d["player_nationality"].value_counts().reset_index()
        vc.columns = ["nationality", "count"]
        return vc.head(15)

    def country_frame(side_df: pd.DataFrame, exclude_ro: bool) -> pd.DataFrame:
        d = side_df.copy()
        if exclude_ro:
            d = d[d["other_club_country"] != "Romania"]
        vc = d["other_club_country"].value_counts().reset_index()
        vc.columns = ["country", "count"]
        return vc.head(15)

    # --- Snapshot KPIs ---
    def romanian_share(side_df: pd.DataFrame) -> float:
        if side_df.empty:
            return float("nan")
        return (side_df["player_nationality"] == "Romania").mean() * 100

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Arrivals (count)", f"{len(arrivals):,}")
    k2.metric("Departures (count)", f"{len(departures):,}")
    k3.metric("Romanian nationals — arrivals", f"{romanian_share(arrivals):.1f}%" if arrivals.shape[0] else "N/A")
    k4.metric("Romanian nationals — departures", f"{romanian_share(departures):.1f}%" if departures.shape[0] else "N/A")

    st.caption(
        "Lower Romanian share on arrivals usually means more foreign signings; on departures, more locals leaving the league."
    )

    st.markdown("#### Player nationality (who the players are)")
    st.write(
        "Counts how many transfers involve players of each nationality. "
        "This is **not** the same as the country of the other club."
    )
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**Arrivals** — nationalities of players joining the perspective club")
        fn_a = nat_frame(arrivals, exclude_ro_nat)
        fig_a = _ranked_bar_h(fn_a, "nationality", "count", "Top nationalities (arrivals)", "#1f77b4")
        if fig_a:
            st.plotly_chart(fig_a, use_container_width=True)
        else:
            st.info("No nationality data for arrivals with current options.")
    with r2:
        st.markdown("**Departures** — nationalities of players leaving the perspective club")
        fn_d = nat_frame(departures, exclude_ro_nat)
        fig_d = _ranked_bar_h(fn_d, "nationality", "count", "Top nationalities (departures)", "#ef553b")
        if fig_d:
            st.plotly_chart(fig_d, use_container_width=True)
        else:
            st.info("No nationality data for departures with current options.")

    st.markdown("#### Other club’s country (where the counterparty is based)")
    st.write(
        "**Arrivals:** country of the **selling** side’s club (the player’s previous club). "
        "**Departures:** country of the **buying** side’s club (where the player goes next)."
    )
    r3, r4 = st.columns(2)
    with r3:
        st.markdown("**Arrivals** — countries linked to incoming players")
        fc_a = country_frame(arrivals, exclude_ro_country)
        fig_ca = _ranked_bar_h(fc_a, "country", "count", "Top countries — other club (arrivals)", "#1f77b4")
        if fig_ca:
            st.plotly_chart(fig_ca, use_container_width=True)
        else:
            st.info("No country data for arrivals with current options.")
    with r4:
        st.markdown("**Departures** — countries linked to outgoing players")
        fc_d = country_frame(departures, exclude_ro_country)
        fig_cd = _ranked_bar_h(fc_d, "country", "count", "Top countries — other club (departures)", "#ef553b")
        if fig_cd:
            st.plotly_chart(fig_cd, use_container_width=True)
        else:
            st.info("No country data for departures with current options.")

    # --- International mix over time ---
    st.markdown("#### International mix over time")
    st.write(
        "Share of transfers where the player’s nationality is **not** Romanian. "
        "Use this to see whether the league is signing or losing more international profiles over the years."
    )

    def intl_by_season(side_df: pd.DataFrame) -> pd.DataFrame:
        if side_df.empty:
            return pd.DataFrame(columns=["season", "intl_share", "transfers"])
        g = side_df.groupby("season").agg(
            transfers=("player_id", "count"),
            intl=("player_nationality", lambda s: (s != "Romania").sum()),
        ).reset_index()
        g["intl_share"] = np.where(g["transfers"] > 0, g["intl"] / g["transfers"] * 100, 0.0)
        return g.sort_values("season")

    mix_a = intl_by_season(arrivals)[["season", "intl_share"]].rename(columns={"intl_share": "Arrivals"})
    mix_d = intl_by_season(departures)[["season", "intl_share"]].rename(columns={"intl_share": "Departures"})
    mix = mix_a.merge(mix_d, on="season", how="outer")
    mix_plot = mix.melt(
        id_vars="season", var_name="transfer_side", value_name="pct_non_romanian"
    )
    mix_plot = mix_plot.dropna(subset=["pct_non_romanian"])

    if not mix_plot.empty:
        fig_mix = px.line(
            mix_plot,
            x="season",
            y="pct_non_romanian",
            color="transfer_side",
            markers=True,
            title="Non-Romanian nationality share by season (%)",
            labels={"pct_non_romanian": "% of transfers (non-Romanian player)", "transfer_side": "Side"},
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
        )
        fig_mix.update_layout(template="plotly_white", yaxis_range=[0, 100])
        st.plotly_chart(fig_mix, use_container_width=True)
    else:
        st.info("Not enough data for international mix trend.")

    # --- Heatmaps: top nationalities x season ---
    st.markdown("#### Nationality footprint by season")
    st.write(
        "Heatmaps use the **top 10 nationalities** (after your “hide Romania” choice for rankings). "
        "Brighter cells = more transfers in that season."
    )

    def nat_heatmap(side_df: pd.DataFrame, exclude_ro: bool, title: str, cmap_color: str):
        d = side_df.copy()
        if exclude_ro:
            d = d[d["player_nationality"] != "Romania"]
        if d.empty:
            return None
        top = d["player_nationality"].value_counts().head(10).index.tolist()
        sub = d[d["player_nationality"].isin(top)]
        if sub.empty:
            return None
        pivot = sub.groupby(["season", "player_nationality"]).size().unstack(fill_value=0)
        pivot = pivot.sort_index()
        fig = px.imshow(
            pivot.T,
            labels=dict(x="Season", y="Nationality", color="Transfers"),
            title=title,
            aspect="auto",
            color_continuous_scale=[[0, "#f0f2f6"], [1, cmap_color]],
        )
        fig.update_layout(template="plotly_white")
        return fig

    h1, h2 = st.columns(2)
    with h1:
        hm_a = nat_heatmap(arrivals, exclude_ro_nat, "Arrivals — top nationalities × season", "#1f77b4")
        if hm_a:
            st.plotly_chart(hm_a, use_container_width=True)
    with h2:
        hm_d = nat_heatmap(departures, exclude_ro_nat, "Departures — top nationalities × season", "#ef553b")
        if hm_d:
            st.plotly_chart(hm_d, use_container_width=True)

    # --- Club-level: diversity ---
    st.markdown("#### Club-level diversity (perspective team)")
    st.write(
        "For each club, how many **different nationalities** appear on **arrivals** vs **departures**, "
        "and total transfer counts. Only clubs with at least 8 transfers on a side are listed."
    )

    def club_diversity(side_df: pd.DataFrame, min_n: int = 8) -> pd.DataFrame:
        if side_df.empty:
            return pd.DataFrame()
        g = (
            side_df.groupby("team1")
            .agg(
                transfers=("player_id", "count"),
                distinct_nationalities=("player_nationality", lambda s: s.nunique()),
            )
            .reset_index()
            .rename(columns={"team1": "Club"})
        )
        return g[g["transfers"] >= min_n].sort_values("distinct_nationalities", ascending=False)

    div_a = club_diversity(arrivals)
    div_d = club_diversity(departures)

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**Arrivals** — breadth of signings")
        if not div_a.empty:
            fig_div_a = px.scatter(
                div_a,
                x="transfers",
                y="distinct_nationalities",
                hover_name="Club",
                title="Signing volume vs nationality diversity",
                labels={
                    "transfers": "Arrival transfers",
                    "distinct_nationalities": "Different nationalities",
                },
                color_discrete_sequence=["#1f77b4"],
            )
            fig_div_a.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig_div_a, use_container_width=True)
        else:
            st.info("Not enough club-level arrival data.")
    with d2:
        st.markdown("**Departures** — breadth of outgoing players")
        if not div_d.empty:
            fig_div_d = px.scatter(
                div_d,
                x="transfers",
                y="distinct_nationalities",
                hover_name="Club",
                title="Outgoing volume vs nationality diversity",
                labels={
                    "transfers": "Departure transfers",
                    "distinct_nationalities": "Different nationalities",
                },
                color_discrete_sequence=["#ef553b"],
            )
            fig_div_d.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig_div_d, use_container_width=True)
        else:
            st.info("Not enough club-level departure data.")

    # --- Detailed reports + CSV ---
    st.markdown("#### Full breakdown tables")
    nat_report_a = (
        arrivals.groupby(["team1", "player_nationality"])
        .size()
        .reset_index(name="transfers")
        .rename(columns={"team1": "Club", "player_nationality": "Nationality"})
        .sort_values(["Club", "transfers"], ascending=[True, False])
    )
    nat_report_d = (
        departures.groupby(["team1", "player_nationality"])
        .size()
        .reset_index(name="transfers")
        .rename(columns={"team1": "Club", "player_nationality": "Nationality"})
        .sort_values(["Club", "transfers"], ascending=[True, False])
    )
    ctry_report_a = (
        arrivals.groupby(["team1", "other_club_country"])
        .size()
        .reset_index(name="transfers")
        .rename(columns={"team1": "Club", "other_club_country": "Other club country"})
        .sort_values(["Club", "transfers"], ascending=[True, False])
    )
    ctry_report_d = (
        departures.groupby(["team1", "other_club_country"])
        .size()
        .reset_index(name="transfers")
        .rename(columns={"team1": "Club", "other_club_country": "Other club country"})
        .sort_values(["Club", "transfers"], ascending=[True, False])
    )

    rep_tab1, rep_tab2, rep_tab3, rep_tab4 = st.tabs(
        ["Arrivals — nationalities", "Departures — nationalities", "Arrivals — countries", "Departures — countries"]
    )
    with rep_tab1:
        st.dataframe(nat_report_a, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV — arrivals by club × nationality",
            nat_report_a.to_csv(index=False).encode("utf-8"),
            "arrivals_club_nationality.csv",
            "text/csv",
            key="dl_nat_a",
        )
    with rep_tab2:
        st.dataframe(nat_report_d, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV — departures by club × nationality",
            nat_report_d.to_csv(index=False).encode("utf-8"),
            "departures_club_nationality.csv",
            "text/csv",
            key="dl_nat_d",
        )
    with rep_tab3:
        st.dataframe(ctry_report_a, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV — arrivals by club × other country",
            ctry_report_a.to_csv(index=False).encode("utf-8"),
            "arrivals_club_country.csv",
            "text/csv",
            key="dl_ctry_a",
        )
    with rep_tab4:
        st.dataframe(ctry_report_d, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV — departures by club × other country",
            ctry_report_d.to_csv(index=False).encode("utf-8"),
            "departures_club_country.csv",
            "text/csv",
            key="dl_ctry_d",
        )


def _position_transfer_side(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["transfer_side"] = np.where(
        out["transfer_type_code"] == 1,
        "Arrivals",
        np.where(out["transfer_type_code"] == 2, "Departures", "Other"),
    )
    out = out[out["transfer_side"].isin(["Arrivals", "Departures"])].copy()
    out["player_position"] = out["player_position"].fillna("(Unknown)").replace("", "(Unknown)")
    return out


def _position_line_group(position: str) -> str:
    p = str(position) if position is not None else ""
    if p == "(Unknown)":
        return "(Unknown)"
    pl = p.lower()
    if "goalkeeper" in pl:
        return "Goalkeeper"
    if "back" in pl or "centre-back" in pl:
        return "Defenders"
    if "midfield" in pl or "winger" in pl:
        return "Midfield / wide"
    if "forward" in pl or "striker" in pl:
        return "Forwards"
    return "Other"


def _pos_bar_h(counts_df: pd.DataFrame, label_col: str, title: str, color: str):
    if counts_df.empty:
        return None
    fig = px.bar(
        counts_df.iloc[::-1],
        x="count",
        y=label_col,
        orientation="h",
        title=title,
        labels={"count": "Transfers", label_col: ""},
        color_discrete_sequence=[color],
    )
    fig.update_layout(template="plotly_white", showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def position_section(df: pd.DataFrame):
    st.subheader("Positions & squad balance")
    st.write(
        "See **which** roles clubs recruit and **who** they move out — by fine-grained role "
        "(Transfermarkt position) and by broader **lines** (defence, midfield, attack). "
        "**Arrivals** and **Departures** are always shown separately so you can compare signing "
        "patterns with outgoing movement."
    )

    work = _position_transfer_side(df)
    if work.empty:
        st.info("No arrivals or departures with position data match the current filters.")
        return

    work["line_group"] = work["player_position"].apply(_position_line_group)
    arrivals = work[work["transfer_side"] == "Arrivals"]
    departures = work[work["transfer_side"] == "Departures"]

    n_pos = work["player_position"].nunique()
    top_arr = arrivals["player_position"].value_counts().head(1)
    top_dep = departures["player_position"].value_counts().head(1)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Distinct positions (in filter)", f"{n_pos}")
    m2.metric(
        "Most common role — arrivals",
        str(top_arr.index[0])[:28] + ("…" if len(str(top_arr.index[0])) > 28 else "")
        if len(top_arr)
        else "N/A",
        delta=f"{int(top_arr.iloc[0])} moves" if len(top_arr) else None,
    )
    m3.metric(
        "Most common role — departures",
        str(top_dep.index[0])[:28] + ("…" if len(str(top_dep.index[0])) > 28 else "")
        if len(top_dep)
        else "N/A",
        delta=f"{int(top_dep.iloc[0])} moves" if len(top_dep) else None,
    )
    m4.metric(
        "Arrivals vs departures (rows)",
        f"{len(arrivals):,} / {len(departures):,}",
    )

    st.markdown("#### Top roles by transfer volume")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**Arrivals** — which positions clubs sign most")
        pc_a = arrivals["player_position"].value_counts().reset_index().head(15)
        pc_a.columns = ["player_position", "count"]
        fa = _pos_bar_h(pc_a, "player_position", "Top positions — arrivals", "#1f77b4")
        if fa:
            st.plotly_chart(fa, use_container_width=True)
        else:
            st.info("No arrival position data.")
    with r2:
        st.markdown("**Departures** — which positions leave most often")
        pc_d = departures["player_position"].value_counts().reset_index().head(15)
        pc_d.columns = ["player_position", "count"]
        fd = _pos_bar_h(pc_d, "player_position", "Top positions — departures", "#ef553b")
        if fd:
            st.plotly_chart(fd, use_container_width=True)
        else:
            st.info("No departure position data.")

    st.markdown("#### Squad lines — share of activity")
    st.write(
        "Roles grouped into **Goalkeeper**, **Defenders**, **Midfield / wide**, **Forwards**, and **Other**. "
        "Compare whether recruitment tilts toward the spine or the flanks."
    )

    def line_shares(side_df: pd.DataFrame) -> pd.DataFrame:
        if side_df.empty:
            return pd.DataFrame(columns=["line_group", "count", "share"])
        vc = side_df["line_group"].value_counts().reset_index()
        vc.columns = ["line_group", "count"]
        vc["share"] = vc["count"] / vc["count"].sum() * 100
        return vc

    ls_a, ls_d = line_shares(arrivals), line_shares(departures)
    r3, r4 = st.columns(2)
    with r3:
        if not ls_a.empty:
            fig_la = px.bar(
                ls_a,
                x="line_group",
                y="share",
                title="Arrivals — % of moves by line",
                labels={"share": "% of arrivals", "line_group": "Line"},
                color_discrete_sequence=["#1f77b4"],
            )
            fig_la.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig_la, use_container_width=True)
    with r4:
        if not ls_d.empty:
            fig_ld = px.bar(
                ls_d,
                x="line_group",
                y="share",
                title="Departures — % of moves by line",
                labels={"share": "% of departures", "line_group": "Line"},
                color_discrete_sequence=["#ef553b"],
            )
            fig_ld.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig_ld, use_container_width=True)

    st.markdown("#### Deal type within each role")
    st.write(
        "**Paid**, **loan**, and **free** splits per position help spot markets (e.g. many free forwards vs paid midfielders)."
    )

    def pos_deal_chart(side_df: pd.DataFrame, title: str, color_seq: list[str]):
        if side_df.empty or "deal_type" not in side_df.columns:
            return None
        # top 10 positions by volume on this side
        top_pos = side_df["player_position"].value_counts().head(10).index
        sub = side_df[side_df["player_position"].isin(top_pos)]
        agg = (
            sub.groupby(["player_position", "deal_type"])
            .size()
            .reset_index(name="count")
        )
        if agg.empty:
            return None
        fig = px.bar(
            agg,
            x="player_position",
            y="count",
            color="deal_type",
            barmode="group",
            title=title,
            labels={"player_position": "Position", "count": "Transfers"},
            color_discrete_sequence=color_seq,
        )
        fig.update_layout(template="plotly_white", xaxis_tickangle=-45, legend_title_text="Deal type")
        return fig

    r5, r6 = st.columns(2)
    with r5:
        fda = pos_deal_chart(arrivals, "Arrivals — deal type by top positions", px.colors.qualitative.Bold)
        if fda:
            st.plotly_chart(fda, use_container_width=True)
    with r6:
        fdd = pos_deal_chart(departures, "Departures — deal type by top positions", px.colors.qualitative.Bold)
        if fdd:
            st.plotly_chart(fdd, use_container_width=True)

    st.markdown("#### Position × season heatmaps")
    st.write(
        "Season × role intensity for the **top 10 positions** on each side (by total volume in your filter)."
    )

    def pos_heatmap(side_df: pd.DataFrame, title: str, cmax: str):
        if side_df.empty:
            return None
        top = side_df["player_position"].value_counts().head(10).index.tolist()
        sub = side_df[side_df["player_position"].isin(top)]
        if sub.empty:
            return None
        pivot = sub.groupby(["season", "player_position"]).size().unstack(fill_value=0).sort_index()
        fig = px.imshow(
            pivot.T,
            labels=dict(x="Season", y="Position", color="Transfers"),
            title=title,
            aspect="auto",
            color_continuous_scale=[[0, "#f0f2f6"], [1, cmax]],
        )
        fig.update_layout(template="plotly_white")
        return fig

    h1, h2 = st.columns(2)
    with h1:
        hm_a = pos_heatmap(arrivals, "Arrivals — top positions × season", "#1f77b4")
        if hm_a:
            st.plotly_chart(hm_a, use_container_width=True)
    with h2:
        hm_d = pos_heatmap(departures, "Departures — top positions × season", "#ef553b")
        if hm_d:
            st.plotly_chart(hm_d, use_container_width=True)

    st.markdown("#### Club focus — repositioning pressure")
    st.write(
        "For each club, **net** transfers by line (arrivals minus departures). "
        "Positive = more players signed than leaving in that line; negative = net outflow."
    )

    if work["team1"].notna().any():
        arr_w = work[work["transfer_side"] == "Arrivals"].groupby(["team1", "line_group"]).size().unstack(fill_value=0)
        dep_w = work[work["transfer_side"] == "Departures"].groupby(["team1", "line_group"]).size().unstack(fill_value=0)
        clubs_all = arr_w.index.union(dep_w.index)
        net_rows = []
        for cl in clubs_all:
            a = arr_w.loc[cl] if cl in arr_w.index else pd.Series(dtype=float)
            d = dep_w.loc[cl] if cl in dep_w.index else pd.Series(dtype=float)
            for lg in work["line_group"].dropna().unique():
                av = float(a.get(lg, 0))
                dv = float(d.get(lg, 0))
                net_rows.append({"Club": cl, "Line": lg, "Net (arr − dep)": av - dv})
        net_df = pd.DataFrame(net_rows)
        net_df = net_df[net_df["Club"].isin(work["team1"].value_counts().head(20).index)]
        if not net_df.empty:
            fig_net = px.bar(
                net_df,
                x="Club",
                y="Net (arr − dep)",
                color="Line",
                barmode="group",
                title="Net movement by squad line (top 20 clubs by volume)",
                labels={"Net (arr − dep)": "Arrivals − departures (count)"},
            )
            fig_net.update_layout(template="plotly_white", xaxis_tickangle=-45, legend_title_text="Line")
            st.plotly_chart(fig_net, use_container_width=True)

    st.markdown("#### Full tables — club × position")
    tbl_a = (
        arrivals.groupby(["team1", "player_position"])
        .size()
        .reset_index(name="transfers")
        .rename(columns={"team1": "Club", "player_position": "Position"})
        .sort_values(["Club", "transfers"], ascending=[True, False])
    )
    tbl_d = (
        departures.groupby(["team1", "player_position"])
        .size()
        .reset_index(name="transfers")
        .rename(columns={"team1": "Club", "player_position": "Position"})
        .sort_values(["Club", "transfers"], ascending=[True, False])
    )
    t1, t2 = st.tabs(["Arrivals", "Departures"])
    with t1:
        st.dataframe(tbl_a, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV — arrivals club × position",
            tbl_a.to_csv(index=False).encode("utf-8"),
            "arrivals_club_position.csv",
            "text/csv",
            key="dl_pos_a",
        )
    with t2:
        st.dataframe(tbl_d, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV — departures club × position",
            tbl_d.to_csv(index=False).encode("utf-8"),
            "departures_club_position.csv",
            "text/csv",
            key="dl_pos_d",
        )


def _deal_transfer_side(df: pd.DataFrame) -> pd.DataFrame:
    """Arrivals / Departures only; expects ``enrich_deal_columns`` already applied."""
    out = df.copy()
    out["transfer_side"] = np.where(
        out["transfer_type_code"] == 1,
        "Arrivals",
        np.where(out["transfer_type_code"] == 2, "Departures", "Other"),
    )
    out = out[out["transfer_side"].isin(["Arrivals", "Departures"])].copy()
    out = out[out["deal_type"].isin(["Paid", "Loan", "Free"])].copy()
    return out


def _deal_mix_pct(side_df: pd.DataFrame) -> dict[str, float]:
    n = len(side_df)
    if n == 0:
        return {"Paid": float("nan"), "Loan": float("nan"), "Free": float("nan")}
    vc = side_df["deal_type"].value_counts(normalize=True) * 100
    return {k: float(vc.get(k, 0.0)) for k in ["Paid", "Loan", "Free"]}


def deal_type_section(df: pd.DataFrame):
    st.subheader("Deal structure: how moves are engineered")
    st.write(
        "**Arrivals** and **Departures** often follow different deal mixes: clubs may sign on "
        "loans or frees while cashing out on **paid** sales (or the opposite). "
        "This tab focuses on that **structure** — not club P&L (see Financials) or position breakdowns "
        "(see Positions). **Paid** = fee > 0 and not a loan; **Loan** = loan flag; **Free** = no fee and not a loan."
    )

    work = _deal_transfer_side(df)
    if work.empty:
        st.info("No arrivals or departures with deal-type data match the current filters.")
        return

    arrivals = work[work["transfer_side"] == "Arrivals"]
    departures = work[work["transfer_side"] == "Departures"]

    mix_a = _deal_mix_pct(arrivals)
    mix_d = _deal_mix_pct(departures)

    # --- Snapshot: volume + composition ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Arrivals (moves)", f"{len(arrivals):,}")
    k2.metric("Departures (moves)", f"{len(departures):,}")
    loan_gap = mix_a["Loan"] - mix_d["Loan"] if (len(arrivals) and len(departures)) else float("nan")
    free_gap = mix_a["Free"] - mix_d["Free"] if (len(arrivals) and len(departures)) else float("nan")
    k3.metric(
        "Loan share — arrivals vs departures",
        f"{mix_a['Loan']:.1f}% vs {mix_d['Loan']:.1f}%"
        if (len(arrivals) and len(departures))
        else (f"{mix_a['Loan']:.1f}% —" if len(arrivals) else "—"),
        delta=f"{loan_gap:+.1f} pp on arrivals" if pd.notna(loan_gap) else None,
        help="Percentage-point gap: positive means arrivals are more loan-heavy than departures.",
    )
    k4.metric(
        "Free share — arrivals vs departures",
        f"{mix_a['Free']:.1f}% vs {mix_d['Free']:.1f}%"
        if (len(arrivals) and len(departures))
        else (f"{mix_a['Free']:.1f}% —" if len(arrivals) else "—"),
        delta=f"{free_gap:+.1f} pp on arrivals" if pd.notna(free_gap) else None,
    )

    insights: list[str] = []
    if pd.notna(loan_gap) and abs(loan_gap) >= 5 and len(arrivals) > 20 and len(departures) > 20:
        if loan_gap > 0:
            insights.append(
                f"Arrivals are **loan-heavy** (**{mix_a['Loan']:.1f}%** vs **{mix_d['Loan']:.1f}%** on departures) — "
                "a typical pattern when clubs take flexibility on incomings while permanent exits clear wages or raise cash."
            )
        else:
            insights.append(
                f"Departures show **more loans** (**{mix_d['Loan']:.1f}%** vs **{mix_a['Loan']:.1f}%** on arrivals) — "
                "often linked to players moving on temporary deals abroad or between domestic clubs."
            )
    if pd.notna(free_gap) and abs(free_gap) >= 5 and len(arrivals) > 20 and len(departures) > 20:
        if free_gap > 0:
            insights.append(
                f"**Free transfers** loom larger on **arrivals** (**{mix_a['Free']:.1f}%**) than on **departures** (**{mix_d['Free']:.1f}%**)."
            )
        else:
            insights.append(
                f"**Free transfers** are more common on **departures** (**{mix_d['Free']:.1f}%**) than **arrivals** (**{mix_a['Free']:.1f}%**)."
            )
    paid_a = arrivals[arrivals["deal_type"] == "Paid"]
    paid_d = departures[departures["deal_type"] == "Paid"]
    med_fee_a = paid_a["transfer_fee_amount"].median() if len(paid_a) else float("nan")
    med_fee_d = paid_d["transfer_fee_amount"].median() if len(paid_d) else float("nan")
    if pd.notna(med_fee_a) and pd.notna(med_fee_d) and med_fee_d > 0 and len(paid_a) >= 10 and len(paid_d) >= 10:
        ratio = med_fee_a / med_fee_d
        if ratio > 1.15:
            insights.append(
                f"Among **paid** deals, median incoming fee (**€{med_fee_a:,.0f}**) is higher than median outgoing (**€{med_fee_d:,.0f}**) — "
                "clubs pay more per signature than they receive per sale at the median (within this filter)."
            )
        elif ratio < 0.85:
            insights.append(
                f"Among **paid** deals, median **sale** fee (**€{med_fee_d:,.0f}**) exceeds median **purchase** (**€{med_fee_a:,.0f}**) — "
                "sales at the median are larger than purchases."
            )
    if insights:
        st.markdown("#### At a glance")
        for block in insights:
            st.markdown(f"- {block}")

    deal_colors = {"Paid": "#6a4c93", "Loan": "#2a9d8f", "Free": "#e9c46a"}
    mix_long = (
        work.groupby(["transfer_side", "deal_type"])
        .size()
        .reset_index(name="count")
    )
    order_side = ["Arrivals", "Departures"]
    mix_long["transfer_side"] = pd.Categorical(
        mix_long["transfer_side"], categories=order_side, ordered=True
    )
    mix_long["deal_type"] = pd.Categorical(
        mix_long["deal_type"], categories=["Paid", "Loan", "Free"], ordered=True
    )
    mix_long = mix_long.sort_values(["transfer_side", "deal_type"])

    st.markdown("#### Head-to-head: counts by deal type")
    st.write(
        "Raw **volumes** (not percentages) — useful when one side is much larger than the other."
    )
    fig_counts = px.bar(
        mix_long,
        x="deal_type",
        y="count",
        color="transfer_side",
        barmode="group",
        title="Paid / loan / free — arrivals vs departures",
        labels={"count": "Transfers", "deal_type": "Deal type", "transfer_side": ""},
        color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
    )
    fig_counts.update_layout(template="plotly_white", legend_title_text="")
    st.plotly_chart(fig_counts, use_container_width=True)

    pct_rows = []
    for side in order_side:
        sd = work[work["transfer_side"] == side]
        n = len(sd)
        if n == 0:
            continue
        for dt in ["Paid", "Loan", "Free"]:
            c = int((sd["deal_type"] == dt).sum())
            pct_rows.append(
                {
                    "transfer_side": side,
                    "deal_type": dt,
                    "share": 100.0 * c / n,
                    "count": c,
                }
            )
    pct_df = pd.DataFrame(pct_rows)
    if not pct_df.empty:
        pct_df["deal_type"] = pd.Categorical(
            pct_df["deal_type"], categories=["Paid", "Loan", "Free"], ordered=True
        )
        st.markdown("#### Same data as mix (100% — easier to compare shape)")
        fig_stack = px.bar(
            pct_df,
            x="transfer_side",
            y="share",
            color="deal_type",
            title="Composition of arrivals vs departures (each column = 100%)",
            labels={"share": "% of moves on this side", "transfer_side": ""},
            color_discrete_map=deal_colors,
        )
        fig_stack.update_layout(
            template="plotly_white",
            barmode="stack",
            legend_title_text="Deal type",
            xaxis={"categoryorder": "array", "categoryarray": order_side},
        )
        st.plotly_chart(fig_stack, use_container_width=True)

    st.markdown("#### How the mix shifts by season")
    st.write(
        "Each season, **within arrivals** and **within departures**, what share is paid vs loan vs free? "
        "That surfaces shifts in how the market is structured over time."
    )
    season_rows = []
    for (season, side), g in work.groupby(["season", "transfer_side"], sort=False):
        n = len(g)
        if n == 0:
            continue
        for dt in ["Paid", "Loan", "Free"]:
            season_rows.append(
                {
                    "season": season,
                    "transfer_side": side,
                    "deal_type": dt,
                    "share": 100.0 * (g["deal_type"] == dt).sum() / n,
                }
            )
    season_mix = pd.DataFrame(season_rows)
    if not season_mix.empty:
        season_mix = season_mix.sort_values("season")
        fig_season_mix = px.line(
            season_mix,
            x="season",
            y="share",
            color="deal_type",
            facet_col="transfer_side",
            markers=True,
            title="Deal-type mix over time (within each side)",
            labels={"share": "% of moves", "season": "Season"},
            color_discrete_map=deal_colors,
            category_orders={"transfer_side": order_side},
        )
        fig_season_mix.update_layout(template="plotly_white", legend_title_text="Deal type")
        fig_season_mix.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig_season_mix, use_container_width=True)

    if "window" in work.columns and work["window"].notna().any():
        st.markdown("#### Summer vs winter — does the deal mix change?")
        st.write(
            "Grouped counts by **transfer window** on each side. Helps spot windows where loans or frees cluster."
        )
        wmix = (
            work.groupby(["window", "transfer_side", "deal_type"])
            .size()
            .reset_index(name="count")
        )
        wmix["window"] = wmix["window"].astype(str)
        fig_w = px.bar(
            wmix,
            x="window",
            y="count",
            color="deal_type",
            facet_col="transfer_side",
            barmode="group",
            title="Deal types by window — arrivals vs departures",
            labels={"count": "Transfers", "window": "Window"},
            color_discrete_map=deal_colors,
            category_orders={"transfer_side": order_side},
        )
        fig_w.update_layout(template="plotly_white", legend_title_text="Deal type")
        fig_w.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig_w, use_container_width=True)

    paid_moves = work[
        (work["deal_type"] == "Paid") & (work["transfer_fee_amount"] > 0)
    ].copy()
    if len(paid_moves) >= 15:
        st.markdown("#### Paid deals only — fee sizes (log scale)")
        st.write(
            "**Financials** focus on totals; here you see the **spread** of reported fees for paid moves only, by direction."
        )
        fig_paid = px.box(
            paid_moves,
            x="transfer_side",
            y="transfer_fee_amount",
            color="transfer_side",
            points="outliers",
            title="Reported fee distribution — paid arrivals vs paid departures",
            labels={
                "transfer_fee_amount": "Fee (€)",
                "transfer_side": "",
            },
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
            log_y=True,
        )
        fig_paid.update_layout(template="plotly_white", showlegend=False)
        st.plotly_chart(fig_paid, use_container_width=True)

    st.markdown("#### Club signing mix vs exit mix (active clubs)")
    st.write(
        "For clubs with enough volume, compare **how they acquire** (arrivals) vs **how they lose players** (departures). "
        "Minimum 12 moves per *side* keeps rows readable."
    )
    min_side = 12
    top_clubs = work.groupby("team1").size().sort_values(ascending=False).head(40).index
    club_rows = []
    for club in top_clubs:
        ca = arrivals[arrivals["team1"] == club]
        cd = departures[departures["team1"] == club]
        if len(ca) < min_side or len(cd) < min_side:
            continue
        ma, md = _deal_mix_pct(ca), _deal_mix_pct(cd)
        club_rows.append(
            {
                "Club": club,
                "Arr — % paid": round(ma["Paid"], 1),
                "Arr — % loan": round(ma["Loan"], 1),
                "Arr — % free": round(ma["Free"], 1),
                "Arr (n)": len(ca),
                "Dep — % paid": round(md["Paid"], 1),
                "Dep — % loan": round(md["Loan"], 1),
                "Dep — % free": round(md["Free"], 1),
                "Dep (n)": len(cd),
                "Δ Loan (Arr−Dep)": round(ma["Loan"] - md["Loan"], 1),
            }
        )
    club_mix = pd.DataFrame(club_rows)
    if club_mix.empty:
        st.info(f"No club reaches {min_side}+ arrivals and {min_side}+ departures in this filter.")
    else:
        club_mix = club_mix.sort_values("Δ Loan (Arr−Dep)", ascending=False)
        st.dataframe(
            club_mix,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Arr — % paid": st.column_config.NumberColumn(format="%.1f"),
                "Arr — % loan": st.column_config.NumberColumn(format="%.1f"),
                "Arr — % free": st.column_config.NumberColumn(format="%.1f"),
                "Dep — % paid": st.column_config.NumberColumn(format="%.1f"),
                "Dep — % loan": st.column_config.NumberColumn(format="%.1f"),
                "Dep — % free": st.column_config.NumberColumn(format="%.1f"),
                "Δ Loan (Arr−Dep)": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        st.caption(
            "Positive **Δ Loan** = more loan-heavy when signing than when letting players go. "
            "Sort order: highest Δ Loan first."
        )
        st.download_button(
            "Download CSV — club deal mix (arrivals vs departures)",
            club_mix.to_csv(index=False).encode("utf-8"),
            "club_deal_mix_arrivals_departures.csv",
            "text/csv",
            key="dl_deal_club_mix",
        )

    st.markdown("#### Season × deal type tables")
    season_tbl = (
        work.groupby(["season", "transfer_side", "deal_type"])
        .size()
        .reset_index(name="count")
        .sort_values(["season", "transfer_side", "deal_type"], ascending=[False, True, True])
    )
    st.dataframe(
        season_tbl.rename(
            columns={
                "season": "Season",
                "transfer_side": "Side",
                "deal_type": "Deal type",
                "count": "Transfers",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download CSV — season × side × deal type",
        season_tbl.to_csv(index=False).encode("utf-8"),
        "deal_mix_season_side_type.csv",
        "text/csv",
        key="dl_deal_season",
    )


def european_impact_section(df: pd.DataFrame):
    st.subheader("European impact — counterparty league strength (UEFA)")
    st.write(
        "Each transfer links the **perspective club** (Team 1) to a **counterparty club** (Team 2). "
        "**Arrivals:** the player comes **from** Team 2’s country. **Departures:** the player goes **to** "
        "Team 2’s country. We map that country to its **UEFA association ranking** for the same calendar "
        "year as the transfer season (**1 = strongest** in the file). "
        "This is about **where the other league sits in Europe**, not player nationality. "
        "By default, **domestic Romanian links** (counterparty country = Romania) are excluded so medians "
        "and percentages are not dominated by internal league moves — you can include them with the toggle below."
    )

    if df.empty:
        st.info("No transfers match the current filters.")
        return

    uefa = load_uefa_long()
    if uefa.empty:
        st.error(
            f"UEFA coefficient file not found or empty. Expected: `{UEFA_CSV_PATH}`."
        )
        return

    work = df.copy()
    work["transfer_side"] = np.where(
        work["transfer_type_code"] == 1,
        "Arrivals",
        np.where(work["transfer_type_code"] == 2, "Departures", "Other"),
    )
    work = work[work["transfer_side"].isin(["Arrivals", "Departures"])].copy()
    if work.empty:
        st.info("No arrivals or departures in the current filter.")
        return

    if "team2_country" not in work.columns:
        st.warning("No `team2_country` column — cannot map to UEFA countries.")
        return

    pairs = (
        work[["season", "team2_country"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    ranked_pairs = attach_counterparty_ranks(pairs, uefa)
    work = work.merge(
        ranked_pairs,
        on=["season", "team2_country"],
        how="left",
    )

    work["counterparty_romania"] = work["team2_country"].map(is_romania_counterparty_country)
    n_rom_links = int(work["counterparty_romania"].sum())

    fx1, fx2 = st.columns(2)
    with fx1:
        exclude_romania_cp = st.checkbox(
            "Exclude domestic Romanian links (counterparty country = Romania)",
            value=True,
            key="uefa_exclude_romania",
            help="Removes moves where the **other** club is in Romania (typical in-league transfers). "
            "All KPIs, charts, and the CSV below use only the remaining rows.",
        )
    with fx2:
        show_romania_ref_line = st.checkbox(
            "Show Romania’s UEFA country rank (grey reference line)",
            value=True,
            key="uefa_show_ro_line",
            help="Romania’s position in the UEFA table over time — independent of the transfer filter.",
        )

    work_use = work[~work["counterparty_romania"]].copy() if exclude_romania_cp else work.copy()
    n_all = len(work_use)
    n_excluded = len(work) - n_all

    if n_all == 0:
        st.warning(
            "No rows left for this view. Turn off “Exclude domestic Romanian links” or widen sidebar filters."
        )
        return

    st.caption(
        f"**Analysis sample:** {n_all:,} move(s)"
        + (
            f" — **{n_excluded:,}** domestic Romanian counterparty link(s) excluded from all numbers below."
            if exclude_romania_cp and n_excluded
            else ""
        )
        + (
            f" — **{n_rom_links:,}** domestic Romanian counterparty link(s) included in the sample."
            if not exclude_romania_cp and n_rom_links
            else ""
        )
    )

    matched = work_use["uefa_rank"].notna()
    n_m = int(matched.sum())
    method_vc = work_use.loc[matched, "uefa_match_method"].value_counts()

    ro_ref = romania_rank_series(uefa)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Moves in analysis",
        f"{n_all:,}",
        delta=f"-{n_excluded:,} domestic RO" if exclude_romania_cp and n_excluded else None,
        help="Rows used for every metric and chart in this tab (after the Romanian-link toggle).",
    )
    k2.metric("Mapped to UEFA rank", f"{n_m:,}", delta=f"{100 * n_m / n_all:.1f}%" if n_all else None)
    arr_r = work_use.loc[work_use["transfer_side"] == "Arrivals", "uefa_rank"]
    dep_r = work_use.loc[work_use["transfer_side"] == "Departures", "uefa_rank"]
    arr_med = arr_r.median()
    dep_med = dep_r.median()
    k3.metric(
        "Median rank — arrivals",
        f"{arr_med:.0f}" if arr_r.notna().any() and pd.notna(arr_med) else "N/A",
        help="Among arrivals with a mapped counterparty country. Lower = stronger league.",
    )
    k4.metric(
        "Median rank — departures",
        f"{dep_med:.0f}" if dep_r.notna().any() and pd.notna(dep_med) else "N/A",
        help="Among departures with a mapped counterparty country.",
    )

    with st.expander("How countries were matched", expanded=False):
        st.write(
            "Exact names, hand-picked aliases (e.g. **Macedonia** / **North Macedonia**, **Turkiye** → **Turkey**, "
            "**Czechia** → **Czech Republic**), then fuzzy spelling. "
            "Countries outside the UEFA ranking list (e.g. Brazil) stay **unmapped** in the export and are excluded from rank-based charts."
        )
        if len(method_vc):
            st.dataframe(
                method_vc.rename_axis("Method").reset_index(name="Mapped rows"),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("#### Romania vs counterparty leagues over time")
    st.write(
        "**Grey line (optional):** Romania’s own UEFA country rank — where the association sits in the table. "
        "**Coloured lines:** median rank of the **counterparty** country on arrivals (blue) and departures (red). "
        "When domestic Romanian links are excluded, the coloured lines reflect **foreign** partners only. "
        "**Lower** rank is better everywhere."
    )
    season_num = pd.to_numeric(work_use["season"], errors="coerce")
    work_plot = work_use.assign(_season=season_num).dropna(subset=["_season"])
    if not work_plot.empty:
        med_side = (
            work_plot[work_plot["uefa_rank"].notna()]
            .groupby(["_season", "transfer_side"], as_index=False)["uefa_rank"]
            .median()
        )
        med_side["_season"] = med_side["_season"].astype(int)
        fig_ctx = px.line(
            med_side,
            x="_season",
            y="uefa_rank",
            color="transfer_side",
            markers=True,
            title="Median UEFA rank of counterparty country — arrivals vs departures",
            labels={"_season": "Season", "uefa_rank": "UEFA country rank (1 = best)", "transfer_side": ""},
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
        )
        fig_ctx.update_layout(template="plotly_white", yaxis_autorange="reversed", legend_title_text="")
        if show_romania_ref_line and not ro_ref.empty:
            fig_ctx.add_trace(
                go.Scatter(
                    x=ro_ref["Year"],
                    y=ro_ref["Romania UEFA rank"],
                    mode="lines+markers",
                    name="Romania (country rank)",
                    line=dict(color="#6c757d", dash="dash"),
                    marker=dict(size=6),
                )
            )
        st.plotly_chart(fig_ctx, use_container_width=True)

    st.markdown("#### Deal-making with top associations")
    st.write(
        "Among moves **with a mapped UEFA rank**, what share has the counterparty country in the **top N** "
        "that season? Uses the same analysis sample as above (Romanian domestic links excluded when the toggle is on)."
    )
    topn = st.slider("Top N threshold", min_value=5, max_value=20, value=10, step=1, key="uefa_topn")

    def topn_share(g: pd.DataFrame) -> float:
        u = g["uefa_rank"].dropna()
        if u.empty:
            return float("nan")
        return float((u <= topn).mean() * 100)

    share_rows = []
    if not work_plot.empty:
        for (sy, side), g in work_plot.groupby(["_season", "transfer_side"]):
            share_rows.append(
                {
                    "season": int(sy),
                    "transfer_side": side,
                    f"pct_top_{topn}": topn_share(g),
                    "n": len(g),
                }
            )
    share_df = pd.DataFrame(share_rows)
    if not share_df.empty:
        share_df = share_df.sort_values("season")
    if not share_df.empty:
        fig_top = px.line(
            share_df,
            x="season",
            y=f"pct_top_{topn}",
            color="transfer_side",
            markers=True,
            title=f"% of moves with counterparty country in UEFA top {topn}",
            labels={
                "season": "Season",
                f"pct_top_{topn}": f"% in top {topn}",
                "transfer_side": "",
            },
            color_discrete_map={"Arrivals": "#1f77b4", "Departures": "#ef553b"},
        )
        fig_top.update_layout(template="plotly_white", yaxis_range=[0, 105], legend_title_text="")
        st.plotly_chart(fig_top, use_container_width=True)

    def rank_bucket(r: float) -> str:
        if pd.isna(r):
            return "Unranked"
        if r <= 5:
            return "Top 5"
        if r <= 15:
            return "6–15"
        if r <= 30:
            return "16–30"
        return "31+"

    work_b = work_plot[work_plot["uefa_rank"].notna()].copy()
    if not work_b.empty:
        work_b["bucket"] = work_b["uefa_rank"].apply(rank_bucket)
        bucket_order = ["Top 5", "6–15", "16–30", "31+"]
        heat_parts = []
        for side in ["Arrivals", "Departures"]:
            sub = work_b[work_b["transfer_side"] == side]
            if sub.empty:
                continue
            ct = (
                sub.groupby(["_season", "bucket"])
                .size()
                .reset_index(name="count")
            )
            tot = sub.groupby("_season").size().reset_index(name="tot")
            m = ct.merge(tot, on="_season")
            m["pct"] = 100 * m["count"] / m["tot"]
            m["transfer_side"] = side
            heat_parts.append(m)
        if heat_parts:
            heat = pd.concat(heat_parts, ignore_index=True)
            heat["bucket"] = pd.Categorical(
                heat["bucket"], categories=bucket_order + ["Unranked"], ordered=True
            )
            for side in ["Arrivals", "Departures"]:
                subh = heat[heat["transfer_side"] == side]
                if subh.empty:
                    continue
                pivot = subh.pivot_table(
                    index="bucket",
                    columns="_season",
                    values="pct",
                    aggfunc="sum",
                ).reindex(bucket_order)
                cmax = "#1f77b4" if side == "Arrivals" else "#ef553b"
                fig_h = px.imshow(
                    pivot,
                    labels=dict(x="Season", y="UEFA rank band", color="% of moves"),
                    title=f"{side} — where counterparty countries sit (row % within season)",
                    aspect="auto",
                    color_continuous_scale=[[0, "#f8f9fa"], [1, cmax]],
                )
                fig_h.update_layout(template="plotly_white")
                st.plotly_chart(fig_h, use_container_width=True)

    st.markdown("#### Full distribution (mapped moves only)")
    c1, c2 = st.columns(2)
    with c1:
        wa = work_use[work_use["transfer_side"] == "Arrivals"]
        wa_m = wa[wa["uefa_rank"].notna()]
        if len(wa_m) > 5:
            fig_a = px.histogram(
                wa_m,
                x="uefa_rank",
                nbins=40,
                color_discrete_sequence=["#1f77b4"],
                title="Arrivals — counterparty country UEFA rank",
                labels={"uefa_rank": "Rank (1 = best)", "count": "Moves"},
            )
            fig_a.update_layout(template="plotly_white")
            st.plotly_chart(fig_a, use_container_width=True)
        else:
            st.info("Not enough mapped arrivals for a histogram.")
    with c2:
        wd = work_use[work_use["transfer_side"] == "Departures"]
        wd_m = wd[wd["uefa_rank"].notna()]
        if len(wd_m) > 5:
            fig_d = px.histogram(
                wd_m,
                x="uefa_rank",
                nbins=40,
                color_discrete_sequence=["#ef553b"],
                title="Departures — counterparty country UEFA rank",
                labels={"uefa_rank": "Rank (1 = best)", "count": "Moves"},
            )
            fig_d.update_layout(template="plotly_white")
            st.plotly_chart(fig_d, use_container_width=True)
        else:
            st.info("Not enough mapped departures for a histogram.")

    st.markdown("#### Country concentration (mapped)")
    st.write("Average UEFA rank and volume for the **counterparty country** over your current filter.")
    lim = st.slider("Show top countries by move count", 5, 40, 18, key="uefa_country_topn")
    for side, color, label in (
        ("Arrivals", "#1f77b4", "Where players **come from** (Team 2 country)"),
        ("Departures", "#ef553b", "Where players **go to** (Team 2 country)"),
    ):
        sub = work_use[(work_use["transfer_side"] == side) & work_use["uefa_rank"].notna()]
        if sub.empty:
            st.info(f"No mapped {side.lower()} to rank.")
            continue
        agg_c = (
            sub.groupby("team2_country", dropna=False)
            .agg(moves=("uefa_rank", "size"), mean_rank=("uefa_rank", "mean"))
            .reset_index()
            .sort_values("moves", ascending=False)
            .head(lim)
        )
        agg_c["mean_rank"] = agg_c["mean_rank"].round(1)
        fig_c = px.bar(
            agg_c.iloc[::-1],
            x="moves",
            y="team2_country",
            orientation="h",
            color="mean_rank",
            color_continuous_scale=[(0, color), (1, "#f0f2f6")],
            title=f"{side}: top counterparty countries (bar length = moves, color ≈ avg UEFA rank)",
            labels={"moves": "Transfers", "team2_country": "Country", "mean_rank": "Avg rank"},
        )
        fig_c.update_layout(
            template="plotly_white",
            yaxis_title="",
            coloraxis_colorbar=dict(title="Avg rank (1=best)"),
        )
        st.caption(label)
        st.plotly_chart(fig_c, use_container_width=True)

    dl = work_use[
        [
            c
            for c in (
                "season",
                "window",
                "transfer_side",
                "player_name",
                "team1",
                "team2",
                "team2_country",
                "counterparty_romania",
                "uefa_year",
                "uefa_rank",
                "uefa_match_method",
            )
            if c in work_use.columns
        ]
    ].sort_values(
        ["season", "transfer_side", "player_name"],
        ascending=[False, True, True],
    )
    dl_name = (
        "european_impact_counterparty_ranks_excl_romania.csv"
        if exclude_romania_cp
        else "european_impact_counterparty_ranks.csv"
    )
    st.download_button(
        "Download CSV — moves with UEFA counterparty mapping (same sample as this tab)",
        dl.to_csv(index=False).encode("utf-8"),
        dl_name,
        "text/csv",
        key="dl_uefa_impact",
    )


def table_section(df: pd.DataFrame):
    st.subheader("Player profiles — full transfer register")
    st.write(
        "Every row is **one move** for the **perspective club** (Team 1 in the data). "
        "**Arrivals** = player joins that club; **Departures** = player leaves that club. "
        "Sidebar filters still apply (including **deal type**); use the controls here to narrow by **side**, "
        "**window**, and **free-text search** across players, clubs, countries, and notes."
    )

    if df.empty:
        st.info("No transfers match the selected filters.")
        return

    t = df.copy()
    t["transfer_side"] = np.where(
        t["transfer_type_code"] == 1,
        "Arrivals",
        np.where(t["transfer_type_code"] == 2, "Departures", "Other"),
    )
    t1s = t["team1"].fillna("").astype(str)
    t2s = t["team2"].fillna("").astype(str)
    t["direction"] = np.where(
        t["transfer_type_code"] == 1,
        t2s + " → " + t1s,
        np.where(t["transfer_type_code"] == 2, t1s + " → " + t2s, "Unknown"),
    )

    n_total = len(t)
    f_row1 = st.columns([1.2, 1.5, 2.5])
    with f_row1[0]:
        side_sel = st.selectbox(
            "Transfer side",
            options=["All", "Arrivals only", "Departures only"],
            index=0,
            key="profile_tbl_side",
        )
    win_pick: list = []
    with f_row1[1]:
        win_opts: list = []
        if "window" in t.columns and t["window"].notna().any():
            win_opts = sorted(
                t["window"].dropna().unique().tolist(),
                key=lambda x: str(x),
            )
        if win_opts:
            win_pick = st.multiselect(
                "Transfer window",
                options=win_opts,
                default=win_opts,
                key="profile_tbl_window",
                help="Clear all to show every window again.",
            )
        elif "window" in t.columns:
            st.caption("No window values in this slice.")
        else:
            st.caption("—")
    with f_row1[2]:
        search_q = st.text_input(
            "Search",
            "",
            placeholder="Player, club, country, position, notes…",
            key="profile_tbl_search",
        )

    t_f = t
    if side_sel == "Arrivals only":
        t_f = t_f[t_f["transfer_side"] == "Arrivals"]
    elif side_sel == "Departures only":
        t_f = t_f[t_f["transfer_side"] == "Departures"]

    if "window" in t_f.columns and win_opts:
        if win_pick:
            t_f = t_f[t_f["window"].isin(win_pick)]

    if search_q.strip():
        q = search_q.strip().lower()
        str_cols = [
            c
            for c in (
                "player_name",
                "team1",
                "team2",
                "team1_country",
                "team2_country",
                "player_nationality",
                "player_position",
                "transfer_notes",
                "direction",
                "deal_type",
                "transfer_side",
            )
            if c in t_f.columns
        ]
        mask = pd.Series(False, index=t_f.index)
        for c in str_cols:
            mask |= t_f[c].fillna("").astype(str).str.lower().str.contains(q, regex=False, na=False)
        if "season" in t_f.columns:
            mask |= t_f["season"].astype(str).str.lower().str.contains(q, regex=False, na=False)
        if "window" in t_f.columns:
            mask |= t_f["window"].fillna("").astype(str).str.lower().str.contains(q, regex=False, na=False)
        if "transfer_fee_amount" in t_f.columns:
            mask |= t_f["transfer_fee_amount"].astype(str).str.contains(q, regex=False, na=False)
        t_f = t_f[mask]

    st.caption(
        f"Showing **{len(t_f):,}** of **{n_total:,}** rows after sidebar + tab filters. "
        "Tip: click column headers in the table to sort."
    )

    display_order = [
        "season",
        "window",
        "transfer_side",
        "player_id",
        "player_name",
        "player_age",
        "player_position",
        "player_nationality",
        "team1",
        "team1_country",
        "team2",
        "team2_country",
        "direction",
        "transfer_type_code",
        "deal_type",
        "is_loan",
        "transfer_fee_amount",
        "expense",
        "income",
        "transfer_notes",
        "team1_id",
        "team2_id",
    ]
    present = [c for c in display_order if c in t_f.columns]
    out = t_f[present].copy()
    out["transfer_side"] = pd.Categorical(
        out["transfer_side"],
        categories=["Arrivals", "Departures", "Other"],
        ordered=True,
    )
    season_sort = pd.to_numeric(out["season"], errors="coerce")
    out = out.assign(_season_sort=season_sort).sort_values(
        ["_season_sort", "transfer_side", "player_name"],
        ascending=[False, True, True],
        na_position="last",
    ).drop(columns=["_season_sort"])

    rename_map = {
        "season": "Season",
        "window": "Window",
        "transfer_side": "Side",
        "player_id": "Player ID",
        "player_name": "Player",
        "player_age": "Age",
        "player_position": "Position",
        "player_nationality": "Nationality",
        "team1": "Perspective club (Team 1)",
        "team1_country": "Team 1 country",
        "team2": "Other club (Team 2)",
        "team2_country": "Team 2 country",
        "direction": "From → To",
        "transfer_type_code": "Type code",
        "deal_type": "Deal type",
        "is_loan": "Loan",
        "transfer_fee_amount": "Fee (€)",
        "expense": "Expense (€)",
        "income": "Income (€)",
        "transfer_notes": "Notes",
        "team1_id": "Team 1 ID",
        "team2_id": "Team 2 ID",
    }
    disp = out.rename(columns=rename_map)

    # --- FIX: Ensure money columns are purely numeric ---
    euro_money_cols = ["Fee (€)", "Expense (€)", "Income (€)"]
    for col in euro_money_cols:
        if col in disp.columns:
            disp[col] = pd.to_numeric(disp[col], errors="coerce")

    col_cfg: dict = {}
    if "Player ID" in disp.columns:
        col_cfg["Player ID"] = st.column_config.NumberColumn(format="%.0f", help="Internal player key.")
    if "Age" in disp.columns:
        col_cfg["Age"] = st.column_config.NumberColumn(format="%.0f")
    if "Type code" in disp.columns:
        col_cfg["Type code"] = st.column_config.NumberColumn(
            format="%.0f",
            help="1 = arrival to Team 1, 2 = departure from Team 1.",
        )
    if "Loan" in disp.columns:
        col_cfg["Loan"] = st.column_config.CheckboxColumn(help="Loan move when flagged in source data.")
    
    # --- FIX: Use Streamlit localized format for pure numbers ---
    for money in euro_money_cols:
        if money in disp.columns:
            col_cfg[money] = st.column_config.NumberColumn(
                format="localized",
                help="Team 1 perspective: paid arrival → expense; paid departure → income. Shown in European style (dot for thousands).",
            )
            
    for tid in ("Team 1 ID", "Team 2 ID"):
        if tid in disp.columns:
            col_cfg[tid] = st.column_config.NumberColumn(format="%.0f")
    if "Side" in disp.columns:
        col_cfg["Side"] = st.column_config.TextColumn(
            help="Arrivals = in to Team 1; Departures = out from Team 1.",
        )
    if "Notes" in disp.columns:
        col_cfg["Notes"] = st.column_config.TextColumn(help="Raw notes from the transfer source.")

    df_kwargs = dict(use_container_width=True, hide_index=True, height=680)
    if col_cfg:
        df_kwargs["column_config"] = col_cfg
    st.dataframe(disp, **df_kwargs)
    
    st.download_button(
        "Download CSV — current table (filtered)",
        disp.to_csv(index=False).encode("utf-8"),
        "player_profiles_transfers.csv",
        "text/csv",
        key="dl_profile_table",
    )


def main():
    st.title("Competition Overview")
    st.caption(
        "Analyze transfers at competition level: financials, age, nationality, "
        "positions, and more. Data is sourced from the Postgres warehouse."
    )

    # Load full dataset first to populate filter options
    base_df = load_data(selected_seasons=None)
    if base_df.empty:
        st.error("No transfer data found in the database.")
        return

    filters = build_filters(base_df)
    filtered_df = apply_filters(base_df, filters)

    # Enrich with financial & deal-type columns
    enriched_df = enrich_deal_columns(filtered_df)

    # Top-level KPIs
    kpi_section(enriched_df)

    # Tabs for deeper exploration
    tab_fin, tab_age, tab_origin, tab_pos, tab_deal, tab_uefa, tab_table = st.tabs(
        [
            "💶 Financials",
            "👤 Age",
            "🌍 Origin & Nationality",
            "📍 Positions",
            "🤝 Deal Types",
            "⭐️ European impact",
            "📋 Player Profiles",
        ]
    )

    with tab_fin:
        financials_section(enriched_df)
    with tab_age:
        age_section(enriched_df)
    with tab_origin:
        origin_nationality_section(enriched_df)
    with tab_pos:
        position_section(enriched_df)
    with tab_deal:
        deal_type_section(enriched_df)
    with tab_uefa:
        european_impact_section(enriched_df)
    with tab_table:
        table_section(enriched_df)


if __name__ == "__main__":
    main()

