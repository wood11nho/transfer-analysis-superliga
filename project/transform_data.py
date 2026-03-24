import pandas as pd
import re
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
# Ensure your password is correct here
DB_CONN = "postgresql://postgres:password@localhost:5432/romanian_football"
engine = create_engine(DB_CONN)

def _parse_fee_string(value):
    """
    Parse fee strings like:
    - "€970k", "€1.2m", "1,200,000", "2e+06"
    Returns float EUR amount or None if not parseable.
    """
    if pd.isna(value):
        return None

    # Direct numeric values
    if isinstance(value, (int, float)):
        return float(value)

    text_value = str(value).strip().lower()
    if text_value == "":
        return None

    # Common non-fee markers
    zero_markers = ["free", "loan", "?", "-", "draft", "sign", "without fee"]
    if any(marker in text_value for marker in zero_markers):
        return 0.0

    # Keep only numeric-relevant characters and unit markers
    normalized = text_value.replace("€", "").replace("eur", "").replace(" ", "")
    normalized = normalized.replace(",", "")

    # Handles numbers with optional unit suffix (k/m/b/bn)
    match = re.search(r"(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)(k|m|b|bn)?", normalized)
    if not match:
        return None

    base = float(match.group(1))
    unit = match.group(2)
    multiplier = 1.0
    if unit == "k":
        multiplier = 1_000.0
    elif unit == "m":
        multiplier = 1_000_000.0
    elif unit in ("b", "bn"):
        multiplier = 1_000_000_000.0

    return base * multiplier


def clean_fee(value, notes=None):
    """
    Converts transfer fee to a pure Float (EUR).
    Priority:
    1) transfer_fee column value
    2) transfer_notes (fallback, e.g. "€970k")
    """

    parsed_main = _parse_fee_string(value)
    if parsed_main is not None:
        return parsed_main

    parsed_notes = _parse_fee_string(notes)
    if parsed_notes is not None:
        return parsed_notes

    # Last resort
    try:
        return float(value)
    except Exception:
        return 0.0

def clean_string(value):
    """Converts empty strings to None for better database handling."""
    if pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
        return None
    return value

def run_pipeline():
    print("🚀 Starting transformation (Historical Accuracy Mode)...")
    
    # 1. READ RAW DATA
    print("... Reading raw_transfers from DB")
    # We read everything. 
    df = pd.read_sql("SELECT * FROM raw_transfers", engine)
    
    # Filter out rows with missing player_url (critical for player dimension)
    initial_count = len(df)
    df = df[df['player_url'].notna() & (df['player_url'] != '')]
    if len(df) < initial_count:
        print(f"   ⚠️  Filtered out {initial_count - len(df)} rows with missing player_url")
    
    # 2. CREATE DIM_PLAYERS
    print("... Building Player Dimension")
    # We group by player_url to ensure uniqueness.
    # We take the 'first' seen value for static things like nationality/position.
    # Note: player_age is NOT stored here - it's stored in fact_transfers to preserve historical age at each transfer
    players = df.groupby('player_url').agg({
        'player_name': 'first',
        'player_position': 'first',
        'player_nationality': 'first'
    }).reset_index()
    
    # Assign Player IDs
    players['player_id'] = range(1, len(players) + 1)
    
    # 3. CREATE DIM_CLUBS
    print("... Building Club Dimension")
    
    # We need a list of EVERY unique club name that appears in either 'team_name' or 'club_2'
    # We also try to capture the country associated with it.
    
    # Step A: Get destination clubs (team_name) and their countries
    dest_clubs = df[['team_name', 'country']].rename(columns={'team_name': 'raw_name', 'country': 'club_country'})
    
    # Step B: Get source clubs (club_2) and their countries
    source_clubs = df[['club_2', 'country_2']].rename(columns={'club_2': 'raw_name', 'country_2': 'club_country'})
    
    # Step C: Combine all club occurrences
    all_clubs_raw = pd.concat([dest_clubs, source_clubs])
    
    # Filter out empty names (sometimes 'Without Club' appears as NaN or empty)
    all_clubs_raw = all_clubs_raw[all_clubs_raw['raw_name'].notna() & (all_clubs_raw['raw_name'] != '')]
    
    # For each unique club name, get the most common country (or first non-null if all are null)
    # This handles cases where the same club appears with different countries
    club_countries = all_clubs_raw.groupby('raw_name')['club_country'].apply(
        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else (x.dropna().iloc[0] if len(x.dropna()) > 0 else None)
    ).reset_index()
    club_countries.columns = ['raw_name', 'club_country']
    
    # Assign Club IDs
    club_countries = club_countries.sort_values('raw_name').reset_index(drop=True)
    club_countries['club_id'] = range(1, len(club_countries) + 1)
    
    # Create the Mapper Dictionary (Name -> ID)
    club_name_to_id = dict(zip(club_countries['raw_name'], club_countries['club_id']))
    
    # Add an "Unknown Club" entry for null mappings (optional, but helps with data integrity)
    # We'll use None for now, but you could add this if needed:
    # unknown_club_id = max(club_name_to_id.values()) + 1 if club_name_to_id else 1
    # club_name_to_id[None] = unknown_club_id

    # 4. CREATE FACT_TRANSFERS
    print("... Building Transfer Fact Table")
    transfers = df.copy()
    
    # Map Players to IDs
    player_url_to_id = dict(zip(players['player_url'], players['player_id']))
    transfers['player_id'] = transfers['player_url'].map(player_url_to_id)
    
    # Map Clubs to IDs - Simple: Keep raw CSV structure
    # team1_id = team_name (always the perspective team)
    # team2_id = club_2 (always the other team)
    # Direction is determined by transfer_type_code:
    #   - transfer_type_code = 1 (Arrivals): team2 → team1 (club_2 → team_name)
    #   - transfer_type_code = 2 (Departures): team1 → team2 (team_name → club_2)
    transfers['team1_id'] = transfers['team_name'].map(club_name_to_id)
    transfers['team2_id'] = transfers['club_2'].map(club_name_to_id)
    
    # Clean Fees (fallback to transfer_notes for values like "€970k")
    transfers['transfer_fee_amount'] = transfers.apply(
        lambda row: clean_fee(row.get('transfer_fee'), row.get('transfer_notes')),
        axis=1
    )
    
    # Encode transfer_type: Arrivals -> 1, Departures -> 2
    transfer_type_map = {'Arrivals': 1, 'Departures': 2}
    transfers['transfer_type_code'] = transfers['transfer_type'].map(transfer_type_map)
    # Check for any unmapped values
    unmapped = transfers['transfer_type_code'].isna().sum()
    if unmapped > 0:
        print(f"   ⚠️  Warning: {unmapped} rows with unmapped transfer_type values")
        # Fill any unmapped values with 0 (or handle as needed)
        transfers['transfer_type_code'] = transfers['transfer_type_code'].fillna(0).astype(int)
    else:
        transfers['transfer_type_code'] = transfers['transfer_type_code'].astype(int)
    
    # Clean and convert numeric fields
    # player_age: Age at the time of transfer (preserves historical accuracy)
    transfers['player_age'] = pd.to_numeric(transfers['player_age'], errors='coerce')
    # Other numeric stats
    numeric_cols = ['in_squad', 'appearances', 'goals', 'minutes_played']
    for col in numeric_cols:
        transfers[col] = pd.to_numeric(transfers[col], errors='coerce').fillna(0).astype('Int64')
    
    # Clean string fields (convert empty strings to None)
    string_cols = ['league', 'league_2', 'season', 'window', 'transfer_notes']
    for col in string_cols:
        transfers[col] = transfers[col].apply(clean_string)
    
    # Ensure is_loan is boolean
    transfers['is_loan'] = transfers['is_loan'].fillna(False).astype(bool)
    
    # Select Final Columns (Including your stats!)
    # 
    # IMPORTANT: team1_id and team2_id match the raw CSV structure:
    #   - team1_id = team_name (the perspective team from CSV)
    #   - team2_id = club_2 (the other team from CSV)
    # 
    # Direction is determined by transfer_type_code:
    #   - transfer_type_code = 1 (Arrivals): direction is team2 → team1 (club_2 → team_name)
    #   - transfer_type_code = 2 (Departures): direction is team1 → team2 (team_name → club_2)
    #
    # league and league_2 are from the raw data perspective:
    #   - league = league of team_name (team1)
    #   - league_2 = league of club_2 (team2)
    final_transfers = transfers[[
        'season', 
        'window',
        'player_id', 
        'player_age',        # Age at the time of transfer (preserves historical accuracy)
        'team1_id',          # team_name from CSV (perspective team)
        'team2_id',          # club_2 from CSV (other team)
        'transfer_fee_amount', 
        'is_loan', 
        'transfer_type_code',  # 1 = Arrivals (team2→team1), 2 = Departures (team1→team2)
        'transfer_notes',     # Additional notes (e.g., "End of loan Jun 30, 2003")
        'league',            # League of team_name (team1)
        'league_2',          # League of club_2 (team2)
        'in_squad',
        'appearances',
        'goals',
        'minutes_played'
    ]]
    
    # 5. UPLOAD TO POSTGRES
    print("... Uploading clean tables to Database")
    
    # Use engine directly for to_sql (it handles connections internally)
    # Or use begin() for explicit transaction management
    with engine.begin() as conn:
        # We use 'if_exists=replace' to overwrite if you run this multiple times
        players.to_sql('dim_players', conn, if_exists='replace', index=False, method='multi')
        club_countries.to_sql('dim_clubs', conn, if_exists='replace', index=False, method='multi')
        final_transfers.to_sql('fact_transfers', conn, if_exists='replace', index_label='transfer_id', method='multi')
        
        # Add Primary Keys for performance (drop first if exists to avoid errors on re-runs)
        print("... Adding Indexes")
        try:
            # Drop constraints if they exist
            conn.execute(text("""
                DO $$ 
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dim_players_pkey') THEN
                        ALTER TABLE dim_players DROP CONSTRAINT dim_players_pkey;
                    END IF;
                END $$;
            """))
            conn.execute(text("""
                DO $$ 
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dim_clubs_pkey') THEN
                        ALTER TABLE dim_clubs DROP CONSTRAINT dim_clubs_pkey;
                    END IF;
                END $$;
            """))
            
            # Add primary keys
            conn.execute(text("ALTER TABLE dim_players ADD PRIMARY KEY (player_id);"))
            conn.execute(text("ALTER TABLE dim_clubs ADD PRIMARY KEY (club_id);"))
            
            # Add Foreign Keys (Optional but good practice)
            # Uncomment if you want referential integrity
            # conn.execute(text("""
            #     ALTER TABLE fact_transfers 
            #     ADD CONSTRAINT fk_player 
            #     FOREIGN KEY (player_id) REFERENCES dim_players(player_id);
            # """))
            # conn.execute(text("""
            #     ALTER TABLE fact_transfers 
            #     ADD CONSTRAINT fk_from_club 
            #     FOREIGN KEY (from_club_id) REFERENCES dim_clubs(club_id);
            # """))
            # conn.execute(text("""
            #     ALTER TABLE fact_transfers 
            #     ADD CONSTRAINT fk_to_club 
            #     FOREIGN KEY (to_club_id) REFERENCES dim_clubs(club_id);
            # """))
        except Exception as e:
            print(f"Index creation note: {e}")

    print("✅ Transformation Complete!")
    print(f"   - Total Players: {len(players)}")
    print(f"   - Total Clubs: {len(club_countries)}")
    print(f"   - Total Transfers: {len(final_transfers)}")
    
    # Report on data quality
    null_team1 = final_transfers['team1_id'].isna().sum()
    null_team2 = final_transfers['team2_id'].isna().sum()
    if null_team1 > 0 or null_team2 > 0:
        print(f"   ⚠️  Data Quality Notes:")
        if null_team1 > 0:
            print(f"      - {null_team1} transfers with missing 'team1_id' (team_name)")
        if null_team2 > 0:
            print(f"      - {null_team2} transfers with missing 'team2_id' (club_2)")

if __name__ == "__main__":
    run_pipeline()