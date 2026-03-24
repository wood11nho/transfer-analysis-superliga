"""
Notebook-style visualizations for General Insights page.

Replicates the exact figures from data_analysis.ipynb / data_analysis.py
so they can be embedded in Streamlit without changing look or logic.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless for Streamlit
import matplotlib.pyplot as plt
import seaborn as sns


def _data_path():
    """Path to the latest combined CSV in project root/data."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    exact_legacy = data_dir / "romania_transfers_combined_2003_2024.csv"
    if exact_legacy.exists():
        return exact_legacy

    combined_files = sorted(data_dir.glob("romania_transfers_combined_*.csv"))
    if combined_files:
        return combined_files[-1]

    # Fallback for explicit error visibility when file is missing
    return data_dir / "romania_transfers_combined_2003_2024.csv"


def map_position_group(position):
    """Maps detailed player positions to broader categories."""
    if pd.isna(position):
        return "Unknown"
    if position == "Goalkeeper":
        return "Goalkeeper"
    if "Centre-Back" in str(position):
        return "Centre-back"
    if "Left-Back" in str(position) or "Right-Back" in str(position):
        return "Full-back"
    if "Centre-Forward" in str(position) or "Second Striker" in str(position):
        return "Centre-forward"
    if "Attacking Midfield" in str(position) or "Winger" in str(position):
        return "Attacking midfielders/wide players"
    if any(x in str(position) for x in ["Defensive Midfield", "Central Midfield", "Left Midfield", "Right Midfield"]):
        return "Midfielder"
    return "Unknown"


def map_nationality_to_region(nationality):
    """Maps player nationalities to broader geographical regions."""
    # Updated to catch None, NaN, empty strings, or whitespace
    if pd.isna(nationality) or str(nationality).strip() == "":
        return "Unknown"

    eastern_europe = [
        "Bulgaria", "Serbia", "Croatia", "Bosnia-Herzegovina", "Slovakia", "Slovenia",
        "Czech Republic", "Poland", "Hungary", "North Macedonia", "Montenegro", "Albania",
        "Ukraine", "Moldova", "Kosovo", "Georgia", "Belarus", "Latvia", "Lithuania", "Estonia", "Russia",
    ]
    western_europe = [
        "France", "Spain", "Netherlands", "Italy", "Belgium", "Germany", "Switzerland", "Austria",
        "Greece", "Portugal", "Sweden", "Denmark", "England", "Scotland", "Ireland", "Finland",
        "Iceland", "Norway", "Luxembourg", "Faroe Islands",
    ]
    south_america = [
        "Brazil", "Argentina", "Uruguay", "Colombia", "Chile", "Paraguay", "Venezuela",
        "Bolivia", "Peru", "Suriname", "Guyana", "Ecuador",
    ]
    africa = [
        "Nigeria", "Ghana", "Cameroon", "Ivory Coast", "Senegal", "Mali", "DR Congo", "Morocco",
        "Algeria", "Tunisia", "Guinea", "Cote d'Ivoire", "Angola", "Burkina Faso", "Sierra Leone",
        "Zimbabwe", "Congo", "Liberia", "Togo", "Niger", "Egypt", "Gabon", "Rwanda", "Mozambique",
        "Kenya", "Central African Republic", "Zambia", "Equatorial Guinea", "Burundi", "Benin",
        "Chad", "Djibouti", "South Africa", "Sudan", "Uganda", "Libya", "Comoros", "Mauritania",
        "The Gambia", "Madagascar", "Malawi", "Mauritius", "Guinea-Bissau", "Cape Verde",
    ]
    asia_middle_east = [
        "Korea, South", "Japan", "Malaysia", "Philippines", "Hongkong", "Cyprus", "Armenia",
        "Israel", "Azerbaijan", "Iraq", "Jordan", "Lebanon", "Saudi Arabia", "Syria", "Palestine", "Türkiye",
        "Tajikistan", # Added
    ]
    north_central_america = [
        "United States", "Canada", "Costa Rica", "Honduras", "Guatemala", "Dominican Republic",
        "Haiti", "El Salvador", "Panama", "Jamaica", "Mexico", "Curacao", "Guadeloupe", "Martinique", "French Guiana",
        "Cuba", # Added
    ]
    oceania = ["Australia", "New Zealand"]

    if nationality == "Romania":
        return "Romania"
    if nationality in eastern_europe:
        return "Rest of Europe" # Or "Eastern Europe" depending on your preference
    if nationality in western_europe:
        return "Western Europe"
    if nationality in south_america:
        return "South America"
    if nationality in africa:
        return "Africa"
    if nationality in asia_middle_east:
        return "Asia & Middle East"
    if nationality in north_central_america:
        return "North & Central America"
    if nationality in oceania:
        return "Oceania"
    
    return "Other"

def prepare_data(csv_path=None):
    """
    Load combined CSV and build all derived data needed for the six notebook visualizations.
    Returns a dict with keys: df, df_arrivals, df_permanent_arrivals, merged_df,
    free_agent_counts, transfer_comparison, region_counts, available_regions, df_age_analysis,
    foreign_arrivals, country_analysis_df, yearly_country_flows, top_countries.
    """
    path = csv_path or _data_path()
    df = pd.read_csv(path)
    season_min = int(pd.to_numeric(df["season"], errors="coerce").min())
    season_max = int(pd.to_numeric(df["season"], errors="coerce").max())

    # Viz 1: paid arrivals
    df_arrivals = df[
        (df["transfer_type"] == "Arrivals") & (df["is_loan"] == False) & (df["transfer_fee"] > 0)
    ].copy()
    df_arrivals["season"] = df_arrivals["season"].astype(int)
    df_arrivals["position_group"] = df_arrivals["player_position"].apply(map_position_group)

    total_spend_per_season = df_arrivals.groupby("season")["transfer_fee"].sum().reset_index()
    total_spend_per_season.rename(columns={"transfer_fee": "total_seasonal_spend"}, inplace=True)
    spend_by_position_season = df_arrivals.groupby(["season", "position_group"])["transfer_fee"].sum().reset_index()
    merged_df = pd.merge(spend_by_position_season, total_spend_per_season, on="season")
    merged_df["percentage_spend"] = (merged_df["transfer_fee"] / merged_df["total_seasonal_spend"]) * 100

    # Viz 2 & 3: permanent arrivals (no loans)
    df_permanent_arrivals = df[
        (df["transfer_type"] == "Arrivals") & (df["is_loan"] == False)
    ].copy()
    df_permanent_arrivals["season"] = df_permanent_arrivals["season"].astype(int)
    df_permanent_arrivals["position_group"] = df_permanent_arrivals["player_position"].apply(map_position_group)
    df_permanent_arrivals["transfer_category"] = np.where(
        df_permanent_arrivals["transfer_fee"] > 0, "Paid Transfer", "Free Transfer"
    )

    df_free_agents = df_permanent_arrivals[df_permanent_arrivals["transfer_category"] == "Free Transfer"].copy()
    free_agent_counts = df_free_agents.groupby(["season", "position_group"]).size().reset_index(name="player_count")

    transfer_comparison = df_permanent_arrivals.groupby(["season", "transfer_category"]).size().unstack(fill_value=0)
    if "Paid Transfer" not in transfer_comparison.columns:
        transfer_comparison["Paid Transfer"] = 0
    if "Free Transfer" not in transfer_comparison.columns:
        transfer_comparison["Free Transfer"] = 0

    # Viz 4: regions
    df_permanent_arrivals["player_region"] = df_permanent_arrivals["player_nationality"].apply(map_nationality_to_region)
    region_counts = df_permanent_arrivals.groupby(["season", "player_region"]).size().unstack(fill_value=0)
    expected_regions = [
        "Romania", "Rest of Europe", "Western Europe", "South America",
        "Africa", "Asia & Middle East", "North & Central America", "Oceania",
    ]
    for r in expected_regions:
        if r not in region_counts.columns:
            region_counts[r] = 0
    available_regions = [r for r in expected_regions if r in region_counts.columns]
    region_counts = region_counts[available_regions]

    # Viz 5: age
    df_permanent_arrivals["player_age_numeric"] = pd.to_numeric(df_permanent_arrivals["player_age"], errors="coerce")
    df_age_analysis = df_permanent_arrivals.dropna(subset=["player_age_numeric"]).copy()
    df_age_analysis["player_age"] = df_age_analysis["player_age_numeric"]
    if season_min <= 2008 and season_max >= 2018:
        bins = [season_min, 2008, 2013, 2018, season_max + 1]
        labels = [f"{season_min}-2007", "2008-2012", "2013-2017", f"2018-{season_max}"]
    else:
        # Fallback: split available years into 4 even buckets
        step = max(1, int(np.ceil((season_max - season_min + 1) / 4)))
        bins = [season_min, season_min + step, season_min + 2 * step, season_min + 3 * step, season_max + 1]
        labels = [
            f"{bins[0]}-{bins[1]-1}",
            f"{bins[1]}-{bins[2]-1}",
            f"{bins[2]}-{bins[3]-1}",
            f"{bins[3]}-{season_max}",
        ]

    df_age_analysis["season_bracket"] = pd.cut(
        df_age_analysis["season"],
        bins=bins,
        labels=labels,
        right=False,
    )

    # Viz 6: foreign corridors
    foreign_arrivals = df_permanent_arrivals[
        (df_permanent_arrivals["country_2"].notna()) & (df_permanent_arrivals["country_2"] != "Romania")
    ].copy()

    country_stats = []
    for country in foreign_arrivals["country_2"].unique():
        country_data = foreign_arrivals[foreign_arrivals["country_2"] == country]
        total_transfers = len(country_data)
        paid_transfers = len(country_data[country_data["transfer_category"] == "Paid Transfer"])
        free_transfers = len(country_data[country_data["transfer_category"] == "Free Transfer"])
        paid_data = country_data[country_data["transfer_category"] == "Paid Transfer"]
        total_fees = paid_data["transfer_fee"].sum()
        avg_fee = paid_data["transfer_fee"].mean() if len(paid_data) > 0 else 0
        seasons = country_data["season"].unique()
        first_season, last_season = seasons.min(), seasons.max()
        active_seasons = len(seasons)
        avg_age = country_data["player_age_numeric"].mean()
        country_stats.append({
            "country": country,
            "total_transfers": total_transfers,
            "paid_transfers": paid_transfers,
            "free_transfers": free_transfers,
            "paid_percentage": (paid_transfers / total_transfers) * 100 if total_transfers > 0 else 0,
            "total_fees": total_fees,
            "avg_fee": avg_fee,
            "first_season": first_season,
            "last_season": last_season,
            "active_seasons": active_seasons,
            "avg_age": avg_age,
            "relationship_duration": last_season - first_season + 1,
            "transfers_per_season": total_transfers / active_seasons if active_seasons > 0 else 0,
        })
    country_analysis_df = pd.DataFrame(country_stats).sort_values("total_transfers", ascending=False)

    def classify_transfer_market(row):
        if row["avg_fee"] >= 200000 and row["paid_percentage"] >= 50:
            return "Premium Market"
        if row["avg_fee"] >= 100000 and row["paid_percentage"] >= 30:
            return "Mid-tier Market"
        if row["paid_percentage"] >= 20:
            return "Mixed Market"
        return "Free Agent Hub"

    country_analysis_df["market_segment"] = country_analysis_df.apply(classify_transfer_market, axis=1)
    yearly_country_flows = foreign_arrivals.groupby(["season", "country_2"]).size().unstack(fill_value=0)
    top_countries = country_analysis_df.head(15)["country"].tolist()

    region_mapping = {
        "Eastern Europe": ["Serbia", "Croatia", "Bulgaria", "Bosnia-Herzegovina", "Ukraine", "Moldova", "Poland", "Czech Republic", "Slovakia", "Slovenia", "Hungary", "North Macedonia", "Montenegro"],
        "Western Europe": ["France", "Italy", "Spain", "Germany", "Netherlands", "Portugal", "Belgium", "Switzerland", "Austria", "England", "Greece"],
        "South America": ["Brazil", "Argentina", "Colombia", "Uruguay", "Chile", "Paraguay", "Venezuela"],
        "Africa": ["Nigeria", "Ghana", "Cameroon", "Morocco", "Algeria", "Tunisia", "Senegal"],
        "Other": [],
    }
    def map_to_region(c):
        for region, countries in region_mapping.items():
            if c in countries:
                return region
        return "Other"
    foreign_arrivals["source_region"] = foreign_arrivals["country_2"].apply(map_to_region)

    return {
        "df": df,
        "df_arrivals": df_arrivals,
        "df_permanent_arrivals": df_permanent_arrivals,
        "merged_df": merged_df,
        "free_agent_counts": free_agent_counts,
        "transfer_comparison": transfer_comparison,
        "region_counts": region_counts,
        "available_regions": available_regions,
        "df_age_analysis": df_age_analysis,
        "foreign_arrivals": foreign_arrivals,
        "country_analysis_df": country_analysis_df,
        "yearly_country_flows": yearly_country_flows,
        "top_countries": top_countries,
        "season_min": season_min,
        "season_max": season_max,
    }


def viz1_position_spend(bundle):
    """Viz 1: Percentage of Money Spent by position (all available seasons)."""
    plt.close("all")
    merged_df = bundle["merged_df"]
    sns.set_style("whitegrid", {"axes.grid": False})
    plt.rc("font", family="sans-serif")
    position_groups = [
        "Goalkeeper", "Centre-back", "Full-back",
        "Midfielder", "Attacking midfielders/wide players", "Centre-forward",
    ]
    colors = sns.color_palette("husl", 6)
    color_map = dict(zip(position_groups, colors))
    fig, axes = plt.subplots(2, 3, figsize=(20, 12), sharey=True)
    axes = axes.flatten()
    fig.suptitle(
        "Which positions do Romanian League clubs spend the most on?",
        fontsize=22, fontweight="bold", ha="center", y=0.98,
    )
    fig.text(0.5, 0.93, "Percent of total transfer fees spent by Romanian League clubs on each position group, by season", fontsize=16, ha="center", color="gray")
    for i, pos_group in enumerate(position_groups):
        ax = axes[i]
        group_data = merged_df[merged_df["position_group"] == pos_group]
        if not group_data.empty:
            sns.scatterplot(x="season", y="percentage_spend", data=group_data, ax=ax, color=color_map[pos_group], alpha=0.6, s=50, legend=False)
            sns.regplot(x="season", y="percentage_spend", data=group_data, ax=ax, scatter=False, lowess=True, color=color_map[pos_group], line_kws={"linewidth": 2.5})
        ax.set_title(pos_group, fontsize=14, fontweight="bold")
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_ylim(0, max(60, merged_df["percentage_spend"].max() * 1.1))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{int(y)}%"))
        ax.tick_params(axis="both", which="major", labelsize=12)
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=5))
    fig.text(0.5, 0.06, "Season", ha="center", va="center", fontsize=16, fontweight="bold")
    fig.text(0.08, 0.5, "Percentage of total spend", ha="center", va="center", rotation="vertical", fontsize=16, fontweight="bold")
    fig.text(0.1, 0.02, "Data compiled from Transfermarkt", fontsize=10, color="gray")
    plt.tight_layout(rect=[0.1, 0.08, 0.95, 0.92])
    return fig


def viz2_free_agents_by_position(bundle):
    """Viz 2: Number of Free Agent Signings by Position."""
    plt.close("all")
    free_agent_counts = bundle["free_agent_counts"]
    sns.set_style("whitegrid", {"axes.grid": False})
    plt.rc("font", family="sans-serif")
    position_groups = [
        "Goalkeeper", "Centre-back", "Full-back",
        "Midfielder", "Attacking midfielders/wide players", "Centre-forward",
    ]
    colors = sns.color_palette("viridis", 6)
    color_map = dict(zip(position_groups, colors))
    fig, axes = plt.subplots(2, 3, figsize=(20, 12), sharey=True)
    axes = axes.flatten()
    fig.suptitle("Which positions do Romanian League clubs sign the most free agents for?", fontsize=22, fontweight="bold", ha="center", y=0.98)
    fig.text(0.5, 0.93, "Number of free transfers (non-loan) for each position group, by season", fontsize=16, ha="center", color="gray")
    for i, pos_group in enumerate(position_groups):
        ax = axes[i]
        group_data = free_agent_counts[free_agent_counts["position_group"] == pos_group]
        if not group_data.empty:
            sns.scatterplot(x="season", y="player_count", data=group_data, ax=ax, color=color_map[pos_group], alpha=0.6, s=50, legend=False)
            sns.regplot(x="season", y="player_count", data=group_data, ax=ax, scatter=False, lowess=True, color=color_map[pos_group], line_kws={"linewidth": 2.5})
        ax.set_title(pos_group, fontsize=14, fontweight="bold")
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_ylim(0, max(60, free_agent_counts["player_count"].max() * 1.1))
        ax.tick_params(axis="both", which="major", labelsize=12)
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=5))
    fig.text(0.5, 0.06, "Season", ha="center", va="center", fontsize=16, fontweight="bold")
    fig.text(0.08, 0.5, "Number of Free Agent Signings", ha="center", va="center", rotation="vertical", fontsize=16, fontweight="bold")
    fig.text(0.1, 0.02, "Data compiled from Transfermarkt", fontsize=10, color="gray")
    plt.tight_layout(rect=[0.1, 0.08, 0.95, 0.92])
    return fig


def viz3_free_vs_paid_over_time(bundle):
    """Viz 3: Free vs Paid Transfers Over Time."""
    plt.close("all")
    transfer_comparison = bundle["transfer_comparison"]
    fig, ax = plt.subplots(figsize=(16, 10))
    x = np.arange(len(transfer_comparison))
    width = 0.35
    bars1 = ax.bar(x - width / 2, transfer_comparison["Free Transfer"], width, label="Free Transfers", color="#3498db", alpha=0.8)
    bars2 = ax.bar(x + width / 2, transfer_comparison["Paid Transfer"], width, label="Paid Transfers", color="#e74c3c", alpha=0.8)
    ax.set_title("Romanian League: Free vs. Paid Transfer Evolution", fontsize=20, fontweight="bold", pad=20)
    ax.set_xlabel("Season", fontsize=14, fontweight="bold")
    ax.set_ylabel("Number of Transfers", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(transfer_comparison.index, rotation=45)
    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, h + 3, f"{int(h)}", ha="center", va="bottom", fontsize=10)
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, h + 3, f"{int(h)}", ha="center", va="bottom", fontsize=10)
    ax.legend(fontsize=12)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    return fig


def viz4_origins_by_region(bundle):
    """Viz 4: Player Origins by Region Over Time."""
    plt.close("all")
    region_counts = bundle["region_counts"]
    available_regions = bundle["available_regions"]
    season_min = bundle["season_min"]
    season_max = bundle["season_max"]
    region_proportions = region_counts.div(region_counts.sum(axis=1), axis=0) * 100
    colors = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E", "#7209B7", "#FF6B35", "#004E89", "#B8860B"][: len(available_regions)]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 14))
    ax1.stackplot(
        region_proportions.index,
        *[region_proportions[r] for r in available_regions],
        labels=available_regions,
        colors=colors,
        alpha=0.8,
    )
    ax1.set_title("Evolution of Player Origins in Romanian League (Proportions)", fontsize=18, fontweight="bold", pad=20)
    ax1.set_ylabel("Percentage of Total Signings (%)", fontsize=12, fontweight="bold")
    ax1.set_ylim(0, 100)
    ax1.legend(loc="upper right", bbox_to_anchor=(1.15, 1))
    ax1.grid(True, alpha=0.3)
    for i, region in enumerate(available_regions):
        ax2.plot(region_counts.index, region_counts[region], marker="o", linewidth=2.5, markersize=4, color=colors[i], label=region)
    ax2.set_title("Evolution of Player Origins in Romanian League (Absolute Numbers)", fontsize=18, fontweight="bold", pad=20)
    ax2.set_xlabel("Season", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Number of Players", fontsize=12, fontweight="bold")
    ax2.legend(loc="upper right", bbox_to_anchor=(1.15, 1))
    ax2.grid(True, alpha=0.3)
    for ax in [ax1, ax2]:
        ax.set_xticks(range(season_min, season_max + 1, 2))
        ax.tick_params(axis="x", rotation=45)
    fig.suptitle(
        f"Geographical Diversification of Romanian League Signings ({season_min}-{season_max})",
        fontsize=20,
        fontweight="bold",
        y=0.98,
    )
    fig.text(0.02, 0.02, "Data compiled from Transfermarkt | Permanent transfers only", fontsize=10, color="gray")
    plt.tight_layout(rect=[0, 0.03, 0.85, 0.96])
    return fig


def viz5_age_paid_vs_free(bundle):
    """Viz 5: Age Distribution of Paid vs. Free Transfers."""
    plt.close("all")
    df_age_analysis = bundle["df_age_analysis"]
    season_min = bundle["season_min"]
    season_max = bundle["season_max"]
    paid_avg_age = df_age_analysis[df_age_analysis["transfer_category"] == "Paid Transfer"]["player_age"].mean()
    free_avg_age = df_age_analysis[df_age_analysis["transfer_category"] == "Free Transfer"]["player_age"].mean()
    paid_median = df_age_analysis[df_age_analysis["transfer_category"] == "Paid Transfer"]["player_age"].median()
    free_median = df_age_analysis[df_age_analysis["transfer_category"] == "Free Transfer"]["player_age"].median()
    age_data = []
    for cat in ["Free Transfer", "Paid Transfer"]:
        ages = df_age_analysis[df_age_analysis["transfer_category"] == cat]["player_age"]
        age_data.extend([(a, cat) for a in ages])
    age_df = pd.DataFrame(age_data, columns=["age", "category"])
    young_paid = len(df_age_analysis[(df_age_analysis["transfer_category"] == "Paid Transfer") & (df_age_analysis["player_age"] <= 23)])
    total_paid = len(df_age_analysis[df_age_analysis["transfer_category"] == "Paid Transfer"])
    young_paid_pct = (young_paid / total_paid) * 100 if total_paid else 0
    experienced_free = len(df_age_analysis[(df_age_analysis["transfer_category"] == "Free Transfer") & (df_age_analysis["player_age"] >= 28)])
    total_free = len(df_age_analysis[df_age_analysis["transfer_category"] == "Free Transfer"])
    experienced_free_pct = (experienced_free / total_free) * 100 if total_free else 0
    insight_text = (
        f"KEY INSIGHTS:\n"
        f"• {young_paid_pct:.1f}% of paid transfers are young players (≤23)\n"
        f"• {experienced_free_pct:.1f}% of free transfers are experienced (≥28)\n"
        f"• Average age gap: {abs(paid_avg_age - free_avg_age):.1f} years"
    )
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
    sns.violinplot(
        data=df_age_analysis.dropna(subset=["season_bracket", "player_age"]),
        x="season_bracket",
        y="player_age",
        hue="transfer_category",
        split=True,
        inner="quart",
        palette={"Free Transfer": "#3498db", "Paid Transfer": "#e74c3c"},
        ax=ax1,
        cut=0,
    )
    ax1.set_title("The Age Blueprint: Do Clubs Pay for Youth and Sign Experience for Free?", fontsize=18, fontweight="bold", pad=20)
    ax1.set_xlabel("Time Period", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Player Age (years)", fontsize=14, fontweight="bold")
    ax1.tick_params(axis="both", which="major", labelsize=12)
    ax1.axhline(paid_avg_age, color="#e74c3c", linestyle="--", alpha=0.7, linewidth=2)
    ax1.axhline(free_avg_age, color="#3498db", linestyle="--", alpha=0.7, linewidth=2)
    ax1.text(0.02, paid_avg_age + 0.5, f"Paid Avg: {paid_avg_age:.1f} years", transform=ax1.get_yaxis_transform(), fontsize=11, color="#c0392b", fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
    ax1.text(0.02, free_avg_age - 1.2, f"Free Avg: {free_avg_age:.1f} years", transform=ax1.get_yaxis_transform(), fontsize=11, color="#2980b9", fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
    handles, labels = ax1.get_legend_handles_labels()
    ax1.legend(handles, ["Free Transfers", "Paid Transfers"], title="Transfer Type", fontsize=12, title_fontsize=14, loc="upper right")
    for cat, color in [("Free Transfer", "#3498db"), ("Paid Transfer", "#e74c3c")]:
        data = age_df[age_df["category"] == cat]["age"]
        sns.histplot(data=data, bins=30, alpha=0.6, color=color, stat="density", ax=ax2, label=cat)
    ax2.set_title("Age Distribution Density Comparison", fontsize=18, fontweight="bold", pad=20)
    ax2.set_xlabel("Player Age (years)", fontsize=14, fontweight="bold")
    ax2.set_ylabel("Density", fontsize=14, fontweight="bold")
    ax2.legend(fontsize=12)
    ax2.tick_params(axis="both", which="major", labelsize=12)
    ax2.axvline(paid_median, color="#e74c3c", linestyle="-", alpha=0.8, linewidth=3)
    ax2.axvline(free_median, color="#3498db", linestyle="-", alpha=0.8, linewidth=3)
    ax2.text(paid_median + 0.3, ax2.get_ylim()[1] * 0.9, f"Paid Median: {paid_median:.0f}", rotation=0, fontsize=11, color="#c0392b", fontweight="bold")
    ax2.text(free_median + 0.3, ax2.get_ylim()[1] * 0.8, f"Free Median: {free_median:.0f}", rotation=0, fontsize=11, color="#2980b9", fontweight="bold")
    fig.text(0.02, 0.98, insight_text, fontsize=12, verticalalignment="top", bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8), fontweight="bold")
    fig.text(
        0.98,
        0.02,
        f"Data: Transfermarkt | Romanian League {season_min}-{season_max}",
        ha="right",
        fontsize=10,
        color="gray",
        style="italic",
    )
    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    return fig


def viz6_transfer_corridors(bundle):
    """Viz 6: Transfer Corridors & Scouting Networks."""
    plt.close("all")
    foreign_arrivals = bundle["foreign_arrivals"]
    country_analysis_df = bundle["country_analysis_df"]
    yearly_country_flows = bundle["yearly_country_flows"]
    top_countries = bundle["top_countries"]
    season_min = bundle["season_min"]
    season_max = bundle["season_max"]
    top_20 = country_analysis_df.head(20)
    segment_data = country_analysis_df.groupby("market_segment").agg({"total_transfers": "sum", "country": "count"}).reset_index()
    age_by_region = []
    regions_for_plot = []
    region_mapping = {
        "Eastern Europe": ["Serbia", "Croatia", "Bulgaria", "Bosnia-Herzegovina", "Ukraine", "Moldova", "Poland", "Czech Republic", "Slovakia", "Slovenia", "Hungary", "North Macedonia", "Montenegro"],
        "Western Europe": ["France", "Italy", "Spain", "Germany", "Netherlands", "Portugal", "Belgium", "Switzerland", "Austria", "England", "Greece"],
        "South America": ["Brazil", "Argentina", "Colombia", "Uruguay", "Chile", "Paraguay", "Venezuela"],
        "Africa": ["Nigeria", "Ghana", "Cameroon", "Morocco", "Algeria", "Tunisia", "Senegal"],
        "Other": [],
    }
    def map_to_region(c):
        for region, countries in region_mapping.items():
            if c in countries:
                return region
        return "Other"
    if "source_region" not in foreign_arrivals.columns:
        foreign_arrivals = foreign_arrivals.copy()
        foreign_arrivals["source_region"] = foreign_arrivals["country_2"].apply(map_to_region)
    for region in ["Eastern Europe", "Western Europe", "South America", "Africa"]:
        region_data = foreign_arrivals[(foreign_arrivals["source_region"] == region) & (foreign_arrivals["player_age_numeric"].notna())]["player_age_numeric"]
        if len(region_data) > 10:
            age_by_region.append(region_data)
            regions_for_plot.append(region)
    fig = plt.figure(figsize=(24, 20))
    gs = fig.add_gridspec(4, 2, height_ratios=[2, 1.5, 1.5, 1.2], width_ratios=[1.5, 1])
    ax1 = fig.add_subplot(gs[0, :])
    paid_bars = ax1.barh(range(len(top_20)), top_20["paid_transfers"], color="#e74c3c", alpha=0.8, label="Paid Transfers")
    free_bars = ax1.barh(range(len(top_20)), top_20["free_transfers"], left=top_20["paid_transfers"], color="#3498db", alpha=0.8, label="Free Transfers")
    ax1.set_yticks(range(len(top_20)))
    ax1.set_yticklabels(top_20["country"])
    ax1.set_xlabel(f"Number of Transfers ({season_min}-{season_max})", fontsize=14, fontweight="bold")
    ax1.set_title("Transfer Corridors into Romanian League: Complete Market Analysis", fontsize=20, fontweight="bold", pad=20)
    for i, (_, row) in enumerate(top_20.iterrows()):
        total = row["total_transfers"]
        paid_pct = (row["paid_transfers"] / total) * 100
        ax1.text(total + 2, i, f"{total} ({paid_pct:.0f}% paid)", va="center", fontsize=10, fontweight="bold")
    ax1.legend(loc="lower right", fontsize=12)
    ax1.grid(axis="x", alpha=0.3)
    ax1.invert_yaxis()
    ax2 = fig.add_subplot(gs[1, 0])
    colors_segment = ["#2E86AB", "#F18F01", "#C73E1D", "#6A994E"]
    wedges, texts, autotexts = ax2.pie(segment_data["total_transfers"], labels=segment_data["market_segment"], autopct="%1.1f%%", colors=colors_segment, startangle=90)
    ax2.set_title("Transfer Market Segmentation", fontsize=16, fontweight="bold")
    ax3 = fig.add_subplot(gs[1, 1:])
    top_8_countries = top_countries[:8]
    colors_time = plt.cm.tab10(np.linspace(0, 1, len(top_8_countries)))
    for i, country in enumerate(top_8_countries):
        if country in yearly_country_flows.columns:
            y_values = yearly_country_flows[country].values
            ax3.plot(yearly_country_flows.index, y_values, marker="o", linewidth=2.5, markersize=5, color=colors_time[i], label=country, alpha=0.8)
    ax3.set_title("Evolution of Key Transfer Corridors", fontsize=16, fontweight="bold")
    ax3.set_xlabel("Season", fontsize=12)
    ax3.set_ylabel("Annual Transfers", fontsize=12)
    ax3.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=10)
    ax3.grid(True, alpha=0.3)
    ax3.set_xticks(range(season_min, season_max + 1, 3))
    ax4 = fig.add_subplot(gs[2, 0])
    top_financial = country_analysis_df[country_analysis_df["total_fees"] > 0].head(12)
    bars = ax4.bar(range(len(top_financial)), top_financial["total_fees"] / 1e6, color="#27AE60", alpha=0.8)
    ax4.set_xticks(range(len(top_financial)))
    ax4.set_xticklabels(top_financial["country"], rotation=45, ha="right")
    ax4.set_ylabel("Total Transfer Fees (€M)", fontsize=12)
    ax4.set_title("Financial Value by Source Country", fontsize=14, fontweight="bold")
    ax4.grid(axis="y", alpha=0.3)
    for i, bar in enumerate(bars):
        h = bar.get_height()
        if h > 0:
            ax4.text(bar.get_x() + bar.get_width() / 2.0, h + 0.1, f"€{h:.1f}M", ha="center", va="bottom", fontsize=9)
    ax6 = fig.add_subplot(gs[2, 1])
    if age_by_region:
        bp = ax6.boxplot(age_by_region, tick_labels=regions_for_plot, patch_artist=True)
        colors_box = ["#FF6B35", "#F18F01", "#C73E1D", "#6A994E"]
        for patch, color in zip(bp["boxes"], colors_box[: len(bp["boxes"])]):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
    ax6.set_ylabel("Player Age", fontsize=12)
    ax6.set_title("Age Profile by Source Region", fontsize=14, fontweight="bold")
    ax6.tick_params(axis="x", rotation=45)
    ax7 = fig.add_subplot(gs[3, :])
    ax7.axis("off")
    n_foreign = len(foreign_arrivals)
    total_fees_m = country_analysis_df["total_fees"].sum() / 1e6
    top5_sum = top_20.head(5)["total_transfers"].sum()
    pct_market = (top5_sum / n_foreign * 100) if n_foreign else 0
    premium = country_analysis_df[country_analysis_df["market_segment"] == "Premium Market"]
    avg_premium = premium["avg_fee"].mean() / 1000 if len(premium) else 0
    free_hubs = len(country_analysis_df[country_analysis_df["market_segment"] == "Free Agent Hub"])
    long_term = len(country_analysis_df[country_analysis_df["relationship_duration"] >= 15])
    most_consistent = country_analysis_df.loc[country_analysis_df["transfers_per_season"].idxmax(), "country"] if len(country_analysis_df) else "N/A"
    max_per_season = country_analysis_df["transfers_per_season"].max() if len(country_analysis_df) else 0
    ee_count = foreign_arrivals[foreign_arrivals["source_region"] == "Eastern Europe"]["country_2"].nunique()
    insights_text = f"""
KEY TRANSFER CORRIDOR INSIGHTS ({season_min}-{season_max}):

MARKET OVERVIEW: {len(country_analysis_df)} source countries • {n_foreign:,} total transfers • €{total_fees_m:.1f}M total investment

TOP CORRIDORS: {top_20.iloc[0]['country']} leads with {top_20.iloc[0]['total_transfers']} transfers • Top 5 represent {top5_sum} transfers ({pct_market:.1f}% of market)

PREMIUM MARKETS: {len(premium)} countries classified as premium • Average fees: €{avg_premium:.0f}K

FREE AGENT HUBS: {free_hubs} countries serve primarily as free agent sources

LONG-TERM PARTNERSHIPS: {long_term} countries maintain 15+ year relationships • Most consistent: {most_consistent} ({max_per_season:.1f} transfers/season)

GEOGRAPHIC DIVERSITY: Strongest connections with Eastern Europe ({ee_count} countries) followed by Western Europe
"""
    ax7.text(0.02, 0.95, insights_text, fontsize=12, verticalalignment="top", bbox=dict(boxstyle="round,pad=1", facecolor="lightblue", alpha=0.1))
    fig.suptitle("Romanian League Transfer Ecosystem: Complete Strategic Analysis", fontsize=24, fontweight="bold", y=0.98)
    fig.text(
        0.99,
        0.01,
        f"Data: Transfermarkt | Analysis covers all foreign transfers {season_min}-{season_max}",
        ha="right",
        fontsize=10,
        color="gray",
        style="italic",
    )
    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    return fig
