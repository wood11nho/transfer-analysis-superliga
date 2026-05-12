import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# --- CONFIGURATION ---
# UPDATE THIS WITH YOUR PASSWORD
DB_USER = 'postgres'
DB_PASSWORD = 'password'  # <--- PUT YOUR POSTGRES PASSWORD HERE
DB_HOST = 'localhost'
DB_PORT = '5432'
NEW_DB_NAME = 'romanian_football'


def get_target_db_url() -> str:
    """
    Returns the destination database URL.

    Resolution order:
    1. TRANSFER_DB_URL
    2. DATABASE_URL
    3. Localhost defaults from this script
    """

    env_url = os.getenv("TRANSFER_DB_URL") or os.getenv("DATABASE_URL")
    if env_url and env_url.strip():
        return env_url.strip()

    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{NEW_DB_NAME}"

def get_latest_combined_csv_path() -> str:
    """Returns latest combined CSV path from /data."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    combined_files = sorted(data_dir.glob("romania_transfers_combined_*.csv"))
    if not combined_files:
        raise FileNotFoundError(
            f"No combined CSV found in {data_dir}. "
            "Run `python data_analysis.py` first."
        )
    return str(combined_files[-1])

def create_database():
    """Connects to default postgres DB to create the new project DB."""
    # If a target URL is provided via env, assume DB already exists (common in cloud providers).
    if os.getenv("TRANSFER_DB_URL") or os.getenv("DATABASE_URL"):
        print("Remote DB URL detected via environment. Skipping CREATE DATABASE step.")
        return

    # Connect to the default 'postgres' database
    url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    
    with engine.connect() as conn:
        try:
            # Check if database exists
            conn.execute(text(f"CREATE DATABASE {NEW_DB_NAME}"))
            print(f"Database '{NEW_DB_NAME}' created successfully.")
        except ProgrammingError as e:
            print(f"Database '{NEW_DB_NAME}' already exists (or error). Skipping creation.")
            # print(e) # Uncomment to debug if needed

def load_data_to_postgres():
    """Reads the combined CSV and uploads to the new database."""
    
    # 1. Read the latest combined CSV file
    csv_path = get_latest_combined_csv_path()
    
    print(f"Reading data from: {csv_path}")
    
    try:
        master_df = pd.read_csv(csv_path)
        print(f"Total Data: {len(master_df)} rows loaded.")
    except FileNotFoundError:
        print(f"File not found: {csv_path}")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    # 3. Connect to destination database (remote via env or local default)
    db_url = get_target_db_url()
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    if "sslmode=" not in db_url and "localhost" not in db_url and "127.0.0.1" not in db_url:
        delimiter = "&" if "?" in db_url else "?"
        db_url = f"{db_url}{delimiter}sslmode=require"

    print(f"Uploading into database host from URL: {db_url.split('@')[-1]}")
    engine = create_engine(db_url)

    # 4. Upload to SQL
    print("Uploading to PostgreSQL... this might take a moment.")
    try:
        # 'replace' will drop the table if it exists and create a new one
        master_df.to_sql('raw_transfers', engine, if_exists='replace', index=False)
        print("SUCCESS! Data uploaded to table 'raw_transfers'.")
    except Exception as e:
        print(f"Error uploading to database: {e}")

# --- RUN THE PROCESS ---
if __name__ == "__main__":
    print("--- Starting Database Setup ---")
    create_database()
    load_data_to_postgres()
    print("--- Process Complete ---")