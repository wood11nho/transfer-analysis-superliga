# Transfer Logic Analysis: Club Mapping & Transfer Type

## 📋 Current Data Structure (CSV)

The raw CSV has these key columns:
- `team_name`: The team whose perspective the transfer is from
- `club_2`: The other club in the transfer
- `transfer_type`: "Arrivals" or "Departures" (from `team_name`'s perspective)
- `country`: Country of `team_name`
- `country_2`: Country of `club_2`

## 🔍 How the Data Works

### Example 1: Arrivals
```
team_name = "FC Dinamo 1948"
club_2 = "Genoa"
transfer_type = "Arrivals"
```
**Meaning:** FC Dinamo 1948 is **RECEIVING** the player from Genoa
- **From Club (Seller):** Genoa
- **To Club (Buyer):** FC Dinamo 1948

### Example 2: Departures
```
team_name = "FC Dinamo 1948"
club_2 = "Inter"
transfer_type = "Departures"
```
**Meaning:** FC Dinamo 1948 is **SELLING** the player to Inter
- **From Club (Seller):** FC Dinamo 1948
- **To Club (Buyer):** Inter

## ⚠️ CRITICAL BUG IN CURRENT CODE

### Current Implementation (transform_data.py lines 114-115):
```python
transfers['from_club_id'] = transfers['club_2'].map(club_name_to_id)
transfers['to_club_id'] = transfers['team_name'].map(club_name_to_id)
```

**This is ALWAYS:**
- `from_club_id` = `club_2`
- `to_club_id` = `team_name`

### The Problem:

✅ **For Arrivals:** This works correctly
- `from_club_id` = `club_2` (seller) ✓
- `to_club_id` = `team_name` (buyer) ✓

❌ **For Departures:** This is **WRONG**
- `from_club_id` = `club_2` (should be `team_name` - the seller) ✗
- `to_club_id` = `team_name` (should be `club_2` - the buyer) ✗

### Impact:
**ALL DEPARTURE TRANSFERS HAVE REVERSED CLUB MAPPINGS!**

Example: When FC Dinamo 1948 sells Ianis Zicu to Inter:
- **Current (WRONG):** from_club_id = Inter, to_club_id = FC Dinamo 1948
- **Should be:** from_club_id = FC Dinamo 1948, to_club_id = Inter

## ✅ Correct Logic Should Be:

```python
# For Arrivals: team_name is buyer, club_2 is seller
# For Departures: team_name is seller, club_2 is buyer

transfers['from_club_id'] = transfers.apply(
    lambda row: club_name_to_id.get(row['team_name']) if row['transfer_type'] == 'Departures' 
                 else club_name_to_id.get(row['club_2']), 
    axis=1
)

transfers['to_club_id'] = transfers.apply(
    lambda row: club_name_to_id.get(row['club_2']) if row['transfer_type'] == 'Departures' 
                 else club_name_to_id.get(row['team_name']), 
    axis=1
)
```

Or more efficiently:
```python
# Create conditional mappings based on transfer_type
arrivals_mask = transfers['transfer_type'] == 'Arrivals'
departures_mask = transfers['transfer_type'] == 'Departures'

# For Arrivals: from=club_2, to=team_name
transfers.loc[arrivals_mask, 'from_club_id'] = transfers.loc[arrivals_mask, 'club_2'].map(club_name_to_id)
transfers.loc[arrivals_mask, 'to_club_id'] = transfers.loc[arrivals_mask, 'team_name'].map(club_name_to_id)

# For Departures: from=team_name, to=club_2
transfers.loc[departures_mask, 'from_club_id'] = transfers.loc[departures_mask, 'team_name'].map(club_name_to_id)
transfers.loc[departures_mask, 'to_club_id'] = transfers.loc[departures_mask, 'club_2'].map(club_name_to_id)
```

## 📊 Database Schema

### fact_transfers table:
- `from_club_id`: The club selling/loaning the player (nullable)
- `to_club_id`: The club buying/receiving the player (nullable)
- `transfer_type_code`: 1 = Arrivals, 2 = Departures

**Note:** The `transfer_type_code` is stored but **should not affect** the from/to mapping in the database. The from/to should always represent the actual transfer direction (seller → buyer), regardless of which team's perspective it's from.

## 🎯 Summary

1. **Current State:** The code incorrectly maps clubs for ALL Departure transfers
2. **Root Cause:** The mapping doesn't account for `transfer_type`
3. **Fix Required:** Conditional mapping based on `transfer_type` value
4. **Data Impact:** All existing departure transfers in the database have reversed from/to clubs

## ✅ Solution Implemented

**Approach:** Normalized direction storage
- `from_club_id` = ALWAYS the seller (regardless of perspective)
- `to_club_id` = ALWAYS the buyer (regardless of perspective)
- `transfer_type_code` = Kept for analysis (1=Arrivals, 2=Departures) to know which team's perspective

**Benefits:**
- Consistent logic for all transfers
- Simple queries (no need to check transfer_type for direction)
- transfer_type_code still available for filtering by perspective
- Standard database design (from → to)

**Files Updated:**
- ✅ `project/transform_data.py` - Fixed mapping logic
- ✅ `project/fix_existing_transfers.py` - Script to fix existing database data

**To Fix Existing Data:**
Run `python project/fix_existing_transfers.py` to correct already-loaded transfers.
