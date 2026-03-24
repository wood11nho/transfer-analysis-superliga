"""
Script to drop and recreate fact_transfers table with new schema (team1_id, team2_id).

This script will:
1. Drop the existing fact_transfers table
2. The table will be recreated when you run transform_data.py

⚠️ WARNING: This will DELETE all existing transfer data!
Make sure you have a backup if needed.
"""

import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
DB_CONN = "postgresql://postgres:password@localhost:5432/romanian_football"
engine = create_engine(DB_CONN)

def drop_fact_transfers_table():
    """Drops the fact_transfers table to allow recreation with new schema"""
    print("🗑️  Dropping fact_transfers table...")
    
    with engine.begin() as conn:
        # Drop the table if it exists
        conn.execute(text("DROP TABLE IF EXISTS fact_transfers CASCADE;"))
        print("✅ fact_transfers table dropped successfully")
        print("   (dim_players and dim_clubs are preserved)")

def verify_tables():
    """Verifies which tables exist"""
    print("\n📊 Checking existing tables...")
    
    with engine.connect() as conn:
        tables = pd.read_sql("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """, conn)
        
        print("\n   Existing tables:")
        for table in tables['table_name']:
            print(f"      - {table}")
        
        if 'fact_transfers' in tables['table_name'].values:
            print("\n   ⚠️  fact_transfers still exists")
        else:
            print("\n   ✅ fact_transfers has been dropped")

if __name__ == "__main__":
    print("=" * 60)
    print("Database Schema Reset Script")
    print("=" * 60)
    print("\nThis script will DROP the fact_transfers table.")
    print("You can then run transform_data.py to recreate it with")
    print("the new schema (team1_id, team2_id).\n")
    
    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        exit(0)
    
    try:
        drop_fact_transfers_table()
        verify_tables()
        print("\n" + "=" * 60)
        print("✅ Done! Now run: python project/transform_data.py")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
