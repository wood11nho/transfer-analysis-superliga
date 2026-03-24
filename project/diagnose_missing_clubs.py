import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

# --- CONFIGURATION ---
DB_CONN = "postgresql://postgres:password@localhost:5432/romanian_football"
engine = create_engine(DB_CONN)

def diagnose_missing_clubs():
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    """
    Identifies transfers with missing from_club_id and exports them to CSV
    for manual review and correction.
    """
    print("🔍 Diagnosing missing club mappings...")
    
    # 1. Read raw data to see original club_2 values
    print("... Reading raw_transfers from DB")
    raw_df = pd.read_sql("SELECT * FROM raw_transfers", engine)
    
    # 2. Read dim_clubs to see what clubs we have
    print("... Reading dim_clubs from DB")
    clubs_df = pd.read_sql("SELECT * FROM dim_clubs", engine)
    
    # 3. Recreate the club mapping (same logic as transform_data.py)
    club_name_to_id = dict(zip(clubs_df['raw_name'], clubs_df['club_id']))
    
    # 4. Find rows where club_2 doesn't map to a club_id
    raw_df['from_club_id'] = raw_df['club_2'].map(club_name_to_id)
    missing_from_club = raw_df[raw_df['from_club_id'].isna()].copy()
    
    if len(missing_from_club) == 0:
        print("✅ No missing from_club_id found!")
        return
    
    print(f"\n📊 Found {len(missing_from_club)} transfers with missing from_club_id")
    
    # 5. Create detailed report from missing rows
    report_data = []
    
    for idx, row in missing_from_club.iterrows():
        club_2_value = row.get('club_2', '')
        
        # Determine why it's missing
        if pd.isna(club_2_value) or club_2_value == '':
            why_missing = 'club_2 is empty/null'
        else:
            # Check if club exists in dim_clubs
            club_exists = len(clubs_df[clubs_df['raw_name'] == club_2_value]) > 0
            why_missing = 'club_2 exists but not mapped (data issue)' if club_exists else 'club_2 not in dim_clubs'
        
        report_data.append({
            'row_index': idx + 1,  # 1-indexed for easier reference
            'season': row.get('season', ''),
            'window': row.get('window', ''),
            'transfer_type': row.get('transfer_type', ''),
            'player_name': row.get('player_name', ''),
            'player_url': row.get('player_url', ''),
            'team_name': row.get('team_name', ''),  # Destination club
            'club_2': club_2_value,  # Source club (the one that's missing!)
            'country_2': row.get('country_2', ''),
            'league_2': row.get('league_2', ''),
            'country': row.get('country', ''),
            'league': row.get('league', ''),
            'transfer_fee': row.get('transfer_fee', ''),
            'is_loan': row.get('is_loan', False),
            'transfer_notes': row.get('transfer_notes', ''),
            'why_missing': why_missing
        })
    
    # Create DataFrame
    report_df = pd.DataFrame(report_data)
    
    # 6. Analyze the missing clubs
    print("\n📋 Analysis of missing clubs:")
    print(f"   - Transfers with empty/null club_2: {len(report_df[report_df['why_missing'] == 'club_2 is empty/null'])}")
    print(f"   - Transfers with club_2 not in dim_clubs: {len(report_df[report_df['why_missing'] == 'club_2 not in dim_clubs'])}")
    
    # Show unique missing club_2 values
    unique_missing_clubs = report_df[report_df['club_2'].notna() & (report_df['club_2'] != '')]['club_2'].unique()
    print(f"\n   - Unique club_2 values that weren't mapped: {len(unique_missing_clubs)}")
    if len(unique_missing_clubs) > 0:
        print("\n   Top missing club names:")
        for club in unique_missing_clubs[:20]:  # Show first 20
            count = len(report_df[report_df['club_2'] == club])
            print(f"      - '{club}': {count} transfers")
    
    # 7. Export to CSV
    output_file = data_dir / "missing_from_club_transfers.csv"
    report_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n💾 Exported detailed report to: {output_file}")
    
    # 8. Create a summary of unique missing clubs for easy addition
    if len(unique_missing_clubs) > 0:
        missing_clubs_summary = []
        for club in unique_missing_clubs:
            club_data = report_df[report_df['club_2'] == club].iloc[0]
            missing_clubs_summary.append({
                'club_name': club,
                'country': club_data.get('country_2', ''),
                'league': club_data.get('league_2', ''),
                'transfer_count': len(report_df[report_df['club_2'] == club]),
                'example_season': club_data.get('season', ''),
                'example_transfer': f"{club_data.get('player_name', '')} -> {club_data.get('team_name', '')}"
            })
        
        clubs_summary_df = pd.DataFrame(missing_clubs_summary)
        summary_file = data_dir / "missing_clubs_summary.csv"
        clubs_summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
        print(f"💾 Exported club summary to: {summary_file}")
        print(f"   (Use this to manually add missing clubs to dim_clubs)")
    
    print("\n✅ Diagnosis complete!")
    return report_df

if __name__ == "__main__":
    diagnose_missing_clubs()
