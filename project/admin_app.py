import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
# Update with your credentials
DB_CONN = "postgresql://postgres:password@localhost:5432/romanian_football"

# --- SETUP & CONNECTION ---
st.set_page_config(page_title="FRF Transfer Admin", layout="wide")

@st.cache_resource
def get_engine():
    return create_engine(DB_CONN)

engine = get_engine()

# --- HELPER FUNCTIONS ---
def load_reference_data():
    """Loads players and clubs for dropdown menus (Cached for speed)"""
    with engine.connect() as conn:
        players = pd.read_sql("SELECT player_id, player_name FROM dim_players ORDER BY player_name", conn)
        clubs = pd.read_sql("SELECT club_id, raw_name as club_name FROM dim_clubs ORDER BY raw_name", conn)
    return players, clubs

def get_transfers_by_player(player_name_search):
    """Search for transfers by player name"""
    query = text("""
        SELECT 
            t.transfer_id,
            t.season,
            t.window,
            p.player_name,
            t.player_age,
            c1.raw_name as team1,
            c2.raw_name as team2,
            t.transfer_fee_amount,
            t.is_loan,
            t.transfer_type_code,
            t.transfer_notes,
            CASE 
                WHEN t.transfer_type_code = 1 THEN c2.raw_name || ' → ' || c1.raw_name
                WHEN t.transfer_type_code = 2 THEN c1.raw_name || ' → ' || c2.raw_name
                ELSE 'Unknown'
            END as direction
        FROM fact_transfers t
        JOIN dim_players p ON t.player_id = p.player_id
        LEFT JOIN dim_clubs c1 ON t.team1_id = c1.club_id
        LEFT JOIN dim_clubs c2 ON t.team2_id = c2.club_id
        WHERE p.player_name ILIKE :name
        ORDER BY t.season DESC
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"name": f"%{player_name_search}%"})

def delete_transfer(transfer_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM fact_transfers WHERE transfer_id = :tid"), {"tid": transfer_id})

def insert_transfer(data):
    # Construct the SQL INSERT
    # Note: team1_id and team2_id are set based on transfer_type_code
    # For Arrivals (1): team1 = buyer, team2 = seller
    # For Departures (2): team1 = seller, team2 = buyer
    query = text("""
        INSERT INTO fact_transfers 
        (season, window, player_id, player_age, team1_id, team2_id, transfer_fee_amount, is_loan, transfer_type_code, transfer_notes)
        VALUES (:season, :window, :pid, :age, :team1_id, :team2_id, :fee, :loan, :type_code, :notes)
    """)
    with engine.begin() as conn:
        conn.execute(query, data)

def update_transfer(transfer_id, data):
    query = text("""
        UPDATE fact_transfers 
        SET season = :season, 
            window = :window,
            player_age = :age,
            transfer_fee_amount = :fee,
            is_loan = :loan,
            transfer_type_code = :type_code,
            team1_id = :team1_id,
            team2_id = :team2_id,
            transfer_notes = :notes
        WHERE transfer_id = :tid
    """)
    data['tid'] = transfer_id
    with engine.begin() as conn:
        conn.execute(query, data)

# --- MAIN APP UI ---

st.title("🇷🇴 FRF Transfer Database Manager")

# Load Reference Data (Players & Clubs)
try:
    players_df, clubs_df = load_reference_data()
    # Create dictionaries for easier lookup in selectboxes
    player_options = dict(zip(players_df['player_name'], players_df['player_id']))
    club_options = dict(zip(clubs_df['club_name'], clubs_df['club_id']))
    # Add a "None" option for clubs (if needed)
    club_options["Unknown/None"] = None
except Exception as e:
    st.error(f"Database Error: {e}")
    st.stop()

# --- TABS FOR FUNCTIONALITY ---
tab1, tab2 = st.tabs(["🔍 Search & Edit", "➕ Add New Transfer"])

# === TAB 1: SEARCH & EDIT ===
with tab1:
    st.header("Manage Existing Transfers")
    
    # 1. Search Bar
    search_query = st.text_input("Search by Player Name", placeholder="e.g., Mutu")
    
    if search_query:
        results = get_transfers_by_player(search_query)
        
        if not results.empty:
            st.dataframe(results, use_container_width=True)
            
            st.divider()
            st.subheader("🛠 Edit or Delete a Record")
            
            # Select ID to edit
            selected_id = st.number_input("Enter Transfer ID to Edit/Delete (from table above)", min_value=0, step=1)
            
            if selected_id in results['transfer_id'].values:
                # Get current row data to pre-fill the form
                row = results[results['transfer_id'] == selected_id].iloc[0]
                
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_fee = st.number_input("Transfer Fee (€)", value=float(row['transfer_fee_amount']))
                        new_season = st.text_input("Season", value=row['season'])
                        window_idx = 0 if row.get('window') == 'Summer' or pd.isna(row.get('window')) else 1
                        new_window = st.selectbox("Window", ["Summer", "Winter"], index=window_idx)
                        # Player age at time of transfer
                        current_age = row.get('player_age', None)
                        new_age = st.number_input("Player Age", min_value=0, max_value=60, 
                                                 value=int(current_age) if pd.notna(current_age) else None,
                                                 help="Player's age at the time of this transfer")
                    with col2:
                        is_loan = st.checkbox("Is Loan?", value=bool(row['is_loan']))
                        transfer_type = st.radio("Type", ["Arrivals (1)", "Departures (2)"], 
                                               index=0 if row['transfer_type_code'] == 1 else 1)
                        
                        # Allow changing clubs (team1 and team2)
                        # Find current club names to set default index, otherwise default to 0
                        try:
                            team1_val = row['team1'] if pd.notna(row['team1']) else None
                            c1_idx = list(club_options.keys()).index(team1_val) if team1_val else 0
                        except (ValueError, KeyError):
                            c1_idx = 0
                        try:
                            team2_val = row['team2'] if pd.notna(row['team2']) else None
                            c2_idx = list(club_options.keys()).index(team2_val) if team2_val else 0
                        except (ValueError, KeyError):
                            c2_idx = 0
                        
                        new_team1 = st.selectbox("Team 1 (Perspective Team)", options=club_options.keys(), index=c1_idx)
                        new_team2 = st.selectbox("Team 2 (Other Team)", options=club_options.keys(), index=c2_idx)
                        st.caption(f"Direction: {'Team 2 → Team 1' if row['transfer_type_code'] == 1 else 'Team 1 → Team 2'}")
                    
                    # Transfer Notes
                    current_notes = row.get('transfer_notes', '') if pd.notna(row.get('transfer_notes')) else ''
                    new_notes = st.text_area("Transfer Notes", value=current_notes, 
                                            placeholder="e.g., End of loan Jun 30, 2003", 
                                            help="Additional notes about the transfer")

                    submit_update = st.form_submit_button("💾 Save Changes", type="primary")
                    
                    if submit_update:
                        type_code = 1 if "Arrivals" in transfer_type else 2
                        data = {
                            "season": new_season,
                            "window": new_window,
                            "age": new_age if new_age else None,
                            "fee": new_fee,
                            "loan": is_loan,
                            "type_code": type_code,
                            "team1_id": club_options[new_team1],
                            "team2_id": club_options[new_team2],
                            "notes": new_notes if new_notes.strip() else None
                        }
                        try:
                            update_transfer(selected_id, data)
                            st.success(f"Transfer {selected_id} updated successfully!")
                            st.rerun() # Refresh table
                        except Exception as e:
                            st.error(f"Error updating: {e}")

                # Delete Button (Outside form to prevent accidental clicks)
                with st.expander("Danger Zone"):
                    if st.button(f"🗑 Delete Transfer {selected_id}", type="primary"):
                        try:
                            delete_transfer(selected_id)
                            st.success("Deleted!")
                            st.rerun()
                        except Exception as e:
                            st.error(e)
            elif selected_id != 0:
                st.warning("ID not found in the search results above.")
        else:
            st.info("No players found with that name.")

# === TAB 2: ADD NEW ===
with tab2:
    st.header("Register New Transfer")
    
    with st.form("add_transfer_form"):
        # Player Selection (Searchable Dropdown)
        player_name = st.selectbox("Select Player", options=player_options.keys())
        
        col1, col2 = st.columns(2)
        with col1:
            team1 = st.selectbox("Team 1 (Perspective Team)", options=club_options.keys())
            team2 = st.selectbox("Team 2 (Other Team)", options=club_options.keys())
            season = st.text_input("Season", value="2024")
        
        with col2:
            fee = st.number_input("Fee (€)", min_value=0.0, step=1000.0)
            window = st.selectbox("Window", ["Summer", "Winter"])
            player_age = st.number_input("Player Age", min_value=0, max_value=60, value=None,
                                        help="Player's age at the time of this transfer")
            t_type = st.radio("Transfer Type", ["Arrivals (1)", "Departures (2)"], 
                             help="Arrivals: Team 2 → Team 1 | Departures: Team 1 → Team 2")
            is_loan = st.checkbox("Loan Deal")
        
        # Transfer Notes
        transfer_notes = st.text_area("Transfer Notes", 
                                    placeholder="e.g., End of loan Jun 30, 2003", 
                                    help="Additional notes about the transfer")

        submit_add = st.form_submit_button("✅ Add Transfer")
        
        if submit_add:
            try:
                # Prepare data dictionary
                type_code = 1 if "Arrivals" in t_type else 2
                data = {
                    "season": season,
                    "window": window,
                    "pid": player_options[player_name],
                    "age": player_age if player_age else None,
                    "team1_id": club_options[team1],
                    "team2_id": club_options[team2],
                    "fee": fee,
                    "loan": is_loan,
                    "type_code": type_code,
                    "notes": transfer_notes if transfer_notes.strip() else None
                }
                
                insert_transfer(data)
                st.success(f"Transfer for {player_name} added successfully!")
            except Exception as e:
                st.error(f"Error adding transfer: {e}")