"""
Reusable SQL queries for the Superliga Transfer Analytics app.

The goal is to keep raw SQL in one place, so Streamlit pages can focus
on presentation, filtering, and charting logic.
"""

from typing import Any

import pandas as pd

from db import run_query


def load_competition_base_df(
    seasons: list[str] | None = None,
) -> pd.DataFrame:
    """
    Loads the core competition dataset from the warehouse tables.

    Columns returned (per transfer):
    - season, window
    - player_id, player_name, player_position, player_nationality, player_age
    - team1_id, team1, team1_country
    - team2_id, team2, team2_country
    - transfer_fee_amount, is_loan
    - transfer_type_code, transfer_notes
    """

    params: dict[str, Any] = {}

    where_clauses: list[str] = []
    if seasons:
        params["seasons"] = tuple(seasons)
        where_clauses.append("t.season IN :seasons")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
        SELECT
            t.season,
            t.window,
            t.player_id,
            p.player_name,
            p.player_position,
            p.player_nationality,
            t.player_age,
            t.team1_id,
            c1.raw_name       AS team1,
            c1.club_country   AS team1_country,
            t.team2_id,
            c2.raw_name       AS team2,
            c2.club_country   AS team2_country,
            t.transfer_fee_amount,
            t.is_loan,
            t.transfer_type_code,
            t.transfer_notes
        FROM fact_transfers t
        JOIN dim_players p ON t.player_id = p.player_id
        LEFT JOIN dim_clubs c1 ON t.team1_id = c1.club_id
        LEFT JOIN dim_clubs c2 ON t.team2_id = c2.club_id
        {where_sql}
    """

    df = run_query(sql, params)

    # Basic type / value normalization
    if not df.empty:
        # Ensure numeric
        df["transfer_fee_amount"] = pd.to_numeric(
            df["transfer_fee_amount"], errors="coerce"
        ).fillna(0.0)
        df["player_age"] = pd.to_numeric(df["player_age"], errors="coerce")

        # Make transfer_type_code an int where possible
        if "transfer_type_code" in df.columns:
            df["transfer_type_code"] = (
                pd.to_numeric(df["transfer_type_code"], errors="coerce")
                .fillna(0)
                .astype("Int64")
            )

    return df

