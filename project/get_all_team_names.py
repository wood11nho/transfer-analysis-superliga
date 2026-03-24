import os
from pathlib import Path
import pandas as pd

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

def get_all_team_names():
    """Extracts all unique team names from the CSV file."""
    
    # Get the absolute path to the latest combined CSV file
    csv_path = get_latest_combined_csv_path()
    
    print(f"Reading data from: {csv_path}")
    
    try:
        # Read the CSV file
        df = pd.read_csv(csv_path)
        print(f"Total rows loaded: {len(df)}")
        
        # Get unique team names from both team_name and club_2 columns
        # (club_2 is the other team involved in the transfer)
        team_names_from_team = df['team_name'].dropna().unique()
        team_names_from_club2 = df['club_2'].dropna().unique()
        
        # Combine and get unique values
        all_team_names = set(team_names_from_team) | set(team_names_from_club2)
        
        # Convert to sorted list for consistent output
        all_team_names_sorted = sorted(list(all_team_names))
        
        print(f"\nTotal unique team names found: {len(all_team_names_sorted)}")
        print("\nAll team names:")
        print("-" * 50)
        
        for team_name in all_team_names_sorted:
            print(team_name)
        
        return all_team_names_sorted
        
    except FileNotFoundError:
        print(f"Error: File not found at {csv_path}")
        return None
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None

if __name__ == "__main__":
    get_all_team_names()
