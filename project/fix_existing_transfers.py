"""
Script to fix existing transfer data in the database.

This corrects the from_club_id and to_club_id mappings for Departure transfers
that were incorrectly stored due to the bug in the original transform_data.py.

IMPORTANT: This script will UPDATE existing data in fact_transfers table.
Make sure you have a backup before running this!
"""

import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
DB_CONN = "postgresql://postgres:password@localhost:5432/romanian_football"
engine = create_engine(DB_CONN)

def fix_transfer_directions():
    """
    Fixes the club mappings for Departure transfers.
    
    The bug: Departure transfers had from_club_id and to_club_id swapped.
    This script swaps them back to the correct direction.
    """
    print("🔧 Fixing transfer directions in database...")
    print("⚠️  This will UPDATE existing data in fact_transfers table")
    
    # Read all transfers
    print("... Reading all transfers from fact_transfers")
    with engine.connect() as conn:
        transfers_df = pd.read_sql("""
            SELECT 
                transfer_id,
                from_club_id,
                to_club_id,
                transfer_type_code
            FROM fact_transfers
            WHERE transfer_type_code = 2  -- Only Departures need fixing
        """, conn)
    
    if len(transfers_df) == 0:
        print("✅ No Departure transfers found. Nothing to fix.")
        return
    
    print(f"   Found {len(transfers_df)} Departure transfers to fix")
    
    # Swap from_club_id and to_club_id for Departures
    # The bug was: for Departures, from=club_2 (buyer), to=team_name (seller)
    # Should be: from=team_name (seller), to=club_2 (buyer)
    # So we need to swap them
    
    print("... Swapping from_club_id and to_club_id for Departure transfers")
    
    with engine.begin() as conn:
        # Use a single UPDATE with CASE to swap the values
        # This is more efficient than row-by-row updates
        update_query = text("""
            UPDATE fact_transfers
            SET 
                from_club_id = to_club_id,
                to_club_id = from_club_id
            WHERE transfer_type_code = 2
              AND from_club_id IS NOT NULL 
              AND to_club_id IS NOT NULL
        """)
        
        result = conn.execute(update_query)
        rows_updated = result.rowcount
        
        print(f"✅ Fixed {rows_updated} Departure transfers")
        print("   (Swapped from_club_id ↔ to_club_id)")
    
    # Verify the fix
    print("\n... Verifying fix...")
    with engine.connect() as conn:
        # Check a few examples
        sample = pd.read_sql("""
            SELECT 
                t.transfer_id,
                t.transfer_type_code,
                c1.raw_name as from_club,
                c2.raw_name as to_club,
                p.player_name
            FROM fact_transfers t
            LEFT JOIN dim_clubs c1 ON t.from_club_id = c1.club_id
            LEFT JOIN dim_clubs c2 ON t.to_club_id = c2.club_id
            JOIN dim_players p ON t.player_id = p.player_id
            WHERE t.transfer_type_code = 2
            LIMIT 5
        """, conn)
        
        if not sample.empty:
            print("\n   Sample of fixed Departure transfers:")
            print(sample.to_string(index=False))
    
    print("\n✅ Fix complete!")

def verify_data_consistency():
    """
    Verifies that the data is now consistent.
    Checks that Arrivals and Departures follow the correct pattern.
    """
    print("\n🔍 Verifying data consistency...")
    
    with engine.connect() as conn:
        # Check that we have both Arrivals and Departures
        counts = pd.read_sql("""
            SELECT 
                transfer_type_code,
                COUNT(*) as count
            FROM fact_transfers
            GROUP BY transfer_type_code
            ORDER BY transfer_type_code
        """, conn)
        
        print("\n   Transfer type distribution:")
        print(counts.to_string(index=False))
        
        # Check for any transfers where from_club_id = to_club_id (shouldn't happen)
        same_club = pd.read_sql("""
            SELECT COUNT(*) as count
            FROM fact_transfers
            WHERE from_club_id = to_club_id
              AND from_club_id IS NOT NULL
        """, conn)
        
        if same_club.iloc[0]['count'] > 0:
            print(f"\n   ⚠️  Warning: {same_club.iloc[0]['count']} transfers with from_club = to_club")
        else:
            print("\n   ✅ No transfers with from_club = to_club (good!)")

if __name__ == "__main__":
    print("=" * 60)
    print("Transfer Direction Fix Script")
    print("=" * 60)
    print("\nThis script fixes the bug where Departure transfers had")
    print("from_club_id and to_club_id swapped.\n")
    
    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        exit(0)
    
    try:
        fix_transfer_directions()
        verify_data_consistency()
        print("\n" + "=" * 60)
        print("✅ All done!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
