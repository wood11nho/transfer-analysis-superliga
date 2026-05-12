<div align="center">

# Superliga Transfer Analytics

**A data warehouse and analytics app for two decades of Romanian Superliga transfers.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Warehouse-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive_Charts-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)

*Built during an internship at the **Romanian Football Federation (FRF)**.*

</div>

---

## Overview

Romanian football is competitive, but the transfer market behind it has been mostly invisible — fees, free agents, scouting corridors, age and position trends across seasons.

This project turns ~20 years of Transfermarkt data into a clean **PostgreSQL warehouse** (`dim_players`, `dim_clubs`, `fact_transfers`) and exposes it through an interactive **Streamlit app**.

It is meant as a decision-support tool: scouts, analysts, journalists and curious fans can slice the data by season, club, position, nationality, deal type, and European pedigree.

## Features

- **Competition page** — KPIs and tabs for Financials, Age, Origin & Nationality, Positions, Deal Types, European impact, and a sortable Player Profiles table.
- **General Insights page** — six notebook-style visualizations: position spend %, free agents by position, free vs paid over time, origins by region, age distribution, transfer corridors.
- **UEFA coefficients** — counterparty leagues are ranked against Romania to surface "above your weight" deals.
- **Feedback widget** — every page has a sidebar feedback form that emails the maintainer directly (no signup, no SMTP in repo — uses [FormSubmit.co](https://formsubmit.co)).
- **Dev Container** — open in GitHub Codespaces and the app runs with a single click.

## Live demo

The app can be deployed on [Streamlit Community Cloud](https://streamlit.io/cloud) or any host that runs `streamlit run app/main.py`. See [Deployment](#deployment) below.

## Screenshots

> *Add screenshots of the Competition page (Financials tab), General Insights tab, and the feedback widget in `docs/screenshots/` and link them here.*

## Tech stack

| Layer            | Choice                                                 |
| ---------------- | ------------------------------------------------------ |
| Source data      | [Transfermarkt](https://www.transfermarkt.com) via `worldfootballR` |
| ETL / cleaning   | Python (pandas), `data_analysis.py`, `transform_data.py` |
| Warehouse        | PostgreSQL — star schema (`dim_players`, `dim_clubs`, `fact_transfers`) |
| App              | Streamlit (multi-page)                                  |
| Charts           | Plotly Express + Plotly Graph Objects, Matplotlib       |
| DB driver        | SQLAlchemy + `psycopg2-binary`                          |
| Feedback relay   | [FormSubmit.co](https://formsubmit.co) (HTTPS, no creds in repo) |

## Repository layout

```
.
├── app/                         # Streamlit application
│   ├── main.py                  # Home page entrypoint
│   ├── config.py                # DB URL resolution (env vars / st.secrets / local default)
│   ├── db.py                    # SQLAlchemy engine + run_query helper
│   ├── queries.py               # Reusable warehouse queries
│   ├── notebook_viz.py          # Notebook-parity visualizations
│   ├── uefa_coefficients.py     # UEFA country coefficient logic
│   ├── ui.py                    # Footer + feedback widget (used by every page)
│   └── pages/
│       ├── 01_Competition.py    # Competition-level analysis (KPIs + tabs)
│       └── 02_GeneralInsights.py# Notebook-style insights
├── project/                     # ETL scripts (one-off database build & maintenance)
├── data/                        # Raw + cleaned CSV exports (transfermarkt scrapes)
├── data_analysis.ipynb          # Exploratory notebook (source of General Insights)
├── data_analysis.py             # Notebook exported to a runnable script
├── transfermarkt_birthday_scraper.py
├── add_birthdays.py
├── worldfootballR_data.ipynb    # R-side scraping reference
├── requirements.txt
├── .devcontainer/               # Codespaces / VS Code dev container
└── README.md
```

## Quick start

### 1. Clone

```bash
git clone https://github.com/wood11nho/transfer-analysis-superliga.git
cd transfer-analysis-superliga
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
.\.venv\Scripts\Activate.ps1       # Windows PowerShell
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Point the app at a PostgreSQL warehouse

The app resolves its connection string in this order:

1. Environment variables: `TRANSFER_DB_URL`, `DATABASE_URL`, `DB_URL`
2. `st.secrets` (top-level or under `[database]` / `[db]`)
3. A local fallback: `postgresql://postgres:password@localhost:5432/romanian_football`

For local development, the easiest path is:

```bash
export DATABASE_URL="postgresql://postgres:password@localhost:5432/romanian_football"
```

For a remote DB (recommended for Streamlit Cloud), use a URL with SSL:

```
postgresql://user:password@host:5432/dbname?sslmode=require
```

### 5. Build the warehouse (one-time)

The ETL lives in [`project/`](project/). Run the scripts in order:

```bash
python project/init_database.py        # creates tables and constraints
python project/transform_data.py       # loads & cleans CSVs into the schema
python project/diagnose_missing_clubs.py  # optional sanity checks
```

### 6. Run the app

```bash
streamlit run app/main.py
```

Open <http://localhost:8501>.

## Deployment

### Streamlit Community Cloud

1. Push this repo to GitHub.
2. Create a new app on [share.streamlit.io](https://share.streamlit.io/) pointing at `app/main.py`.
3. In **Settings → Secrets**, paste either:

   ```toml
   DATABASE_URL = "postgresql://user:password@host:5432/dbname?sslmode=require"
   ```

   or the nested form:

   ```toml
   [database]
   url = "postgresql://user:password@host:5432/dbname?sslmode=require"
   ```

4. Click **Deploy**.

The app normalizes `postgres://` URLs and automatically adds `sslmode=require` for non-local hosts.

### GitHub Codespaces / Dev Container

The repo ships a `.devcontainer/` definition that runs `streamlit run app/main.py` on attach. Just open the repo in Codespaces and forward port `8501`.

## Feedback & bug reports

Every page has a **"💬 Feedback / Report an issue"** expander in the left sidebar. Submissions are delivered straight to the maintainer's inbox via FormSubmit.co — no account or SMTP setup required.

Prefer GitHub? Open an issue: <https://github.com/wood11nho/transfer-analysis-superliga/issues>

### Re-wiring the feedback inbox

If you fork this project, change the destination email in [`app/ui.py`](app/ui.py):

```python
FEEDBACK_EMAIL = "your.email@example.com"
```

On the first submission FormSubmit will email you a one-click confirmation link to activate the address.

## Data sources & licensing

- Transfer and player data: **Transfermarkt** (scraped via [`worldfootballR`](https://github.com/JaseZiv/worldfootballR)).
- UEFA country coefficients: official UEFA tables.

This project is for research and educational purposes. All trademarks and data belong to their respective owners.

## Acknowledgements

- **Federația Română de Fotbal (FRF)** — for the internship and the domain context that shaped the analyses.
- The maintainers of `worldfootballR`, Streamlit, Plotly, pandas, and PostgreSQL.

## License

Released under the **MIT License**.

---

<div align="center">
<sub>Made with ⚽ and 🐍 by <a href="https://github.com/wood11nho">Stoica Elias</a></sub>
</div>
