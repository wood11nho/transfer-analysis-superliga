# New Database Schema: team1_id and team2_id

## 📊 New Structure

The database now uses a simpler structure that matches the raw CSV:

### fact_transfers table:
- `team1_id`: The perspective team from CSV (`team_name`)
- `team2_id`: The other team from CSV (`club_2`)
- `transfer_type_code`: 1 = Arrivals, 2 = Departures

### Direction Logic:
The direction of the transfer is determined by `transfer_type_code`:

- **transfer_type_code = 1 (Arrivals):**
  - Direction: `team2 → team1` (club_2 → team_name)
  - Meaning: Player arrives at team1 from team2

- **transfer_type_code = 2 (Departures):**
  - Direction: `team1 → team2` (team_name → club_2)
  - Meaning: Player departs from team1 to team2

## 📝 Examples

### Example 1: Arrival
```
team1 = "FC Dinamo 1948"
team2 = "Genoa"
transfer_type_code = 1 (Arrivals)
```
**Direction:** Genoa → FC Dinamo 1948 (team2 → team1)

### Example 2: Departure
```
team1 = "FC Dinamo 1948"
team2 = "Inter"
transfer_type_code = 2 (Departures)
```
**Direction:** FC Dinamo 1948 → Inter (team1 → team2)

## 🔄 Migration Steps

1. **Drop existing table:**
   ```bash
   python project/reset_database_schema.py
   ```

2. **Recreate with new schema:**
   ```bash
   python project/transform_data.py
   ```

## ✅ Benefits

- **Simpler:** Matches raw CSV structure exactly
- **Clear:** team1 is always the perspective team
- **Flexible:** Direction determined by transfer_type_code
- **Consistent:** No need to swap values based on type

## 📋 Updated Files

- ✅ `project/transform_data.py` - Uses team1_id and team2_id
- ✅ `project/admin_app.py` - Updated to work with new schema
- ✅ `project/reset_database_schema.py` - Script to drop old table

## 🔍 Query Examples

### Get all transfers for a player:
```sql
SELECT 
    t.transfer_id,
    p.player_name,
    c1.raw_name as team1,
    c2.raw_name as team2,
    t.transfer_type_code,
    CASE 
        WHEN t.transfer_type_code = 1 THEN c2.raw_name || ' → ' || c1.raw_name
        WHEN t.transfer_type_code = 2 THEN c1.raw_name || ' → ' || c2.raw_name
    END as direction
FROM fact_transfers t
JOIN dim_players p ON t.player_id = p.player_id
LEFT JOIN dim_clubs c1 ON t.team1_id = c1.club_id
LEFT JOIN dim_clubs c2 ON t.team2_id = c2.club_id
WHERE p.player_name = 'Player Name'
```

### Get all arrivals to a team:
```sql
SELECT * FROM fact_transfers
WHERE team1_id = (SELECT club_id FROM dim_clubs WHERE raw_name = 'Team Name')
  AND transfer_type_code = 1
```

### Get all departures from a team:
```sql
SELECT * FROM fact_transfers
WHERE team1_id = (SELECT club_id FROM dim_clubs WHERE raw_name = 'Team Name')
  AND transfer_type_code = 2
```
