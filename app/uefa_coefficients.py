"""
Load UEFA association country rankings and map transfer counterparty countries.

CSV shape: Year, Position (1 = strongest), Country.
Lower Position = higher European impact / stronger coefficient pool.
"""

from __future__ import annotations

import difflib
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
UEFA_CSV_PATH = _ROOT / "data" / "uefa_coefficient_by_country_2003_2025.csv"


def _norm_key(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("’", "'")
    return s


def is_romania_counterparty_country(raw: object) -> bool:
    """
    True when ``team2_country`` is Romania — i.e. the other club is in the Romanian league
    (moves between Romanian clubs). Used to strip these from “foreign league strength” views.
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return False
    t = _norm_key(str(raw))
    if not t or t in ("nan", "none", "(unknown)", "unknown"):
        return False
    if t in ("romania", "republic of romania", "rou", "ro"):
        return True
    return False


# Transfer / data spelling -> ordered list of UEFA CSV spellings to try for that year (lowercase keys).
_CANDIDATE_CHAINS: dict[str, list[str]] = {
    "north macedonia": ["north macedonia", "macedonia"],
    "macedonia": ["north macedonia", "macedonia"],
    "fyr macedonia": ["north macedonia", "macedonia"],
    "republic of north macedonia": ["north macedonia", "macedonia"],
    "turkiye": ["turkey"],
    "türkiye": ["turkey"],
    "czechia": ["czech republic"],
    "ireland": ["republic of ireland", "ireland"],
    "republic of ireland": ["republic of ireland", "ireland"],
    "bosnia-herzegovina": ["bosnia and herzegovina"],
    "bosnia herzegovina": ["bosnia and herzegovina"],
    "bih": ["bosnia and herzegovina"],
    "serbia": ["serbia", "serbia and montenegro"],
    "montenegro": ["montenegro", "serbia and montenegro"],
    "serbia and montenegro": ["serbia and montenegro", "serbia", "montenegro"],
    "russia": ["russia"],
    "uk": ["england"],
    "united kingdom": ["england", "scotland", "wales", "northern ireland"],
    "great britain": ["england", "scotland", "wales"],
    "u.s.a.": [],
    "usa": [],
    "united states": [],
    "brazil": [],
    "argentina": [],
    "japan": [],
    "china": [],
    "south korea": [],
    "korea republic": [],
    "australia": [],
    "canada": [],
    "mexico": [],
    "colombia": [],
    "uruguay": [],
    "paraguay": [],
    "chile": [],
    "peru": [],
    "ecuador": [],
    "venezuela": [],
    "nigeria": [],
    "senegal": [],
    "ghana": [],
    "cameroon": [],
    "ivory coast": [],
    "côte d'ivoire": [],
    "south africa": [],
    "egypt": [],
    "morocco": [],
    "algeria": [],
    "tunisia": [],
    "iran": [],
    "saudi arabia": [],
    "qatar": [],
    "uae": [],
    "united arab emirates": [],
    "new zealand": [],
    "india": [],
    "unknown": [],
    "(unknown)": [],
    "": [],
}


def _variants(base: str) -> list[str]:
    """Generate spelling variants for one normalized token."""
    out = [base]
    if "-" in base:
        out.append(base.replace("-", " "))
    if " and " in base:
        out.append(base.replace(" and ", " & "))
    return list(dict.fromkeys(out))


@lru_cache(maxsize=1)
def load_uefa_long() -> pd.DataFrame:
    if not UEFA_CSV_PATH.is_file():
        return pd.DataFrame(columns=["Year", "Position", "Country", "country_key"])
    df = pd.read_csv(UEFA_CSV_PATH)
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df["Position"] = pd.to_numeric(df["Position"], errors="coerce")
    df["country_key"] = df["Country"].astype(str).map(_norm_key)
    return df.dropna(subset=["Year", "Position"])


def build_year_rank_maps(uefa: pd.DataFrame) -> dict[int, dict[str, int]]:
    """year -> {normalized country name -> UEFA position (1 = best)}."""
    out: dict[int, dict[str, int]] = {}
    for year, g in uefa.groupby("Year"):
        y = int(year)
        out[y] = dict(zip(g["country_key"].tolist(), g["Position"].astype(int).tolist()))
    return out


def uefa_year_bounds(uefa: pd.DataFrame) -> tuple[int, int]:
    if uefa.empty:
        return 2003, 2025
    ys = uefa["Year"].dropna().astype(int)
    return int(ys.min()), int(ys.max())


def resolve_uefa_rank(
    year_rank_map: dict[str, int],
    raw_country: object,
) -> tuple[float, str]:
    """
    Return (position, method). position is NaN if outside UEFA list / unknown.
    method: exact | alias | variant | fuzzy | unmatched | missing_country
    """
    if raw_country is None or (isinstance(raw_country, float) and np.isnan(raw_country)):
        return float("nan"), "missing_country"
    s = str(raw_country).strip()
    if not s or s.lower() in ("nan", "none", "(unknown)", "unknown"):
        return float("nan"), "missing_country"

    key = _norm_key(s)
    if key in _CANDIDATE_CHAINS and _CANDIDATE_CHAINS[key] == []:
        return float("nan"), "outside_europe"

    # Direct / variant on table
    for v in _variants(key):
        if v in year_rank_map:
            return float(year_rank_map[v]), "exact"

    # Chained aliases (UEFA spellings)
    chain = _CANDIDATE_CHAINS.get(key, [key])
    for cand in chain:
        ck = _norm_key(str(cand))
        for v in _variants(ck):
            if v in year_rank_map:
                return float(year_rank_map[v]), "alias"

    # Fuzzy against this season's associations (typos, extra words)
    pool = list(year_rank_map.keys())
    if pool:
        for v in _variants(key):
            m = difflib.get_close_matches(v, pool, n=1, cutoff=0.86)
            if m:
                return float(year_rank_map[m[0]]), "fuzzy"

    return float("nan"), "unmatched"


def romania_rank_series(uefa: pd.DataFrame) -> pd.DataFrame:
    """Romania's UEFA country position by year (for reference charts)."""
    ro = uefa[uefa["country_key"] == "romania"][["Year", "Position"]].copy()
    ro = ro.sort_values("Year")
    ro["Year"] = ro["Year"].astype(int)
    return ro.rename(columns={"Position": "Romania UEFA rank"})


def attach_counterparty_ranks(
    season_country: pd.DataFrame,
    uefa: pd.DataFrame,
) -> pd.DataFrame:
    """
    season_country: columns season, team2_country (unique pairs).
    Returns same rows + uefa_year, uefa_rank, uefa_match_method.
    """
    if season_country.empty or uefa.empty:
        out = season_country.copy()
        out["uefa_year"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
        out["uefa_rank"] = np.nan
        out["uefa_match_method"] = "no_uefa_file"
        return out

    y_min, y_max = uefa_year_bounds(uefa)
    maps = build_year_rank_maps(uefa)

    def row_apply(r) -> pd.Series:
        sy = pd.to_numeric(r["season"], errors="coerce")
        if pd.isna(sy):
            uy = y_min
        else:
            uy = int(max(y_min, min(y_max, int(sy))))
        ymap = maps.get(uy, {})
        pos, how = resolve_uefa_rank(ymap, r["team2_country"])
        return pd.Series({"uefa_year": uy, "uefa_rank": pos, "uefa_match_method": how})

    out = season_country.copy()
    applied = out.apply(row_apply, axis=1)
    return pd.concat([out.reset_index(drop=True), applied], axis=1)
