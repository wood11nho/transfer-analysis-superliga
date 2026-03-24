import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
from pathlib import Path

# --- Configuration ---
OUTPUT_FILE = 'data/romania_transfers_with_birthdays.csv'

# Standard header to look like a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 1. The Scraper Function ---
def get_player_birthday(url):
    """Scrapes the birthday using the robust itemprop='birthDate' method."""
    if not isinstance(url, str) or "transfermarkt" not in url:
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        # If we get a 404 or 429 (Too Many Requests), handle it
        if response.status_code != 200:
            print(f"  Warning: Status code {response.status_code} for {url}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # STRATEGY: Look for the specific machine-readable tag
        date_element = soup.find(attrs={"itemprop": "birthDate"})

        if date_element:
            raw_text = date_element.get_text(strip=True)
            # Cleanup: "23/06/1976 (49)" -> "23/06/1976"
            clean_date = re.split(r'\s*\(', raw_text)[0]
            return clean_date.strip()
            
        return None

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None

# --- 2. Main Processing Logic ---
def main():
    data_dir = Path("data")
    combined_files = sorted(data_dir.glob("romania_transfers_combined_*.csv"))
    if not combined_files:
        print("Error: No combined file found in data/. Run data_analysis.py first.")
        return

    input_file = str(combined_files[-1])

    print(f"Reading {input_file}...")
    try:
        df = pd.read_csv(input_file)
    except FileNotFoundError:
        print("Error: Input file not found. Please check the path.")
        return

    print(f"Found {len(df)} rows. Starting scraping...")

    # Dictionary to cache results: { 'player_url': '23/06/1976' }
    # This ensures we don't scrape the same player 10 times if they have 10 transfers.
    player_cache = {} 
    birthdays = []

    # Iterate through the DataFrame
    for index, row in df.iterrows():
        url = row['player_url']
        player_name = row['player_name']
        
        # Progress indicator (every 10 rows)
        if index % 10 == 0:
            print(f"Processing row {index}/{len(df)}...")

        # CHECK CACHE FIRST (Speed Optimization)
        if url in player_cache:
            birthdays.append(player_cache[url])
            continue

        # If not in cache, SCRAPE
        birthday = get_player_birthday(url)
        
        # Store result
        birthdays.append(birthday)
        player_cache[url] = birthday
        
        if birthday:
            print(f"  [+] Found: {player_name} -> {birthday}")
        else:
            print(f"  [-] Failed: {player_name}")

        # RANDOM DELAY (Safety Mechanism)
        # Sleep between 1 and 3 seconds to avoid IP Ban. 
        # Reducing this is risky.
        time.sleep(random.uniform(1, 3))

    # --- 3. Save Results ---
    df['birthday_date'] = birthdays
    
    # Save to new CSV
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nDone! Saved {len(df)} rows to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()