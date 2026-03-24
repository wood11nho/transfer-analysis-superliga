import requests
from bs4 import BeautifulSoup
import re

def get_player_birthday(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- STRATEGY 1: The "Golden Ticket" (Best Method) ---
        # Your debug output showed: <span ... itemprop="birthDate">
        # This tag is designed for machines. We search for it directly.
        date_element = soup.find(attrs={"itemprop": "birthDate"})

        if date_element:
            raw_text = date_element.get_text(strip=True)
            # Cleanup: "23/06/1976 (49)" -> "23/06/1976"
            clean_date = re.split(r'\s*\(', raw_text)[0]
            return clean_date.strip()

        # --- STRATEGY 2: Fallback (Text Search) ---
        # If the semantic tag is missing, we use the structure you found.
        # Find the label, then grab the very next span tag.
        label = soup.find(string=re.compile("Date of birth"))
        if label:
            # The date is in a span immediately following the text node
            next_span = label.find_next("span")
            if next_span:
                raw_text = next_span.get_text(strip=True)
                clean_date = re.split(r'\s*\(', raw_text)[0]
                return clean_date.strip()

        return "Date not found"

    except Exception as e:
        return f"Error: {e}"

# --- Usage ---
url = "https://www.transfermarkt.com/claudiu-niculescu/profil/spieler/26049"
print(f"Birthday: {get_player_birthday(url)}")