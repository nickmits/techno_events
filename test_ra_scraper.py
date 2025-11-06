"""
Test RA.co scraper to verify it returns venue addresses
"""
import sys
import os
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.tools.ra_events import fetch_ra_events

# Load environment variables
load_dotenv()

def test_ra_scraper():
    """Test RA scraper with address fields"""

    print("="*80)
    print("Testing RA.co Scraper - Venue Address Extraction")
    print("="*80 + "\n")

    # Fetch events for Nov 15, 2025 (the date from the screenshot)
    print("Fetching events for 2025-11-15...\n")

    result = fetch_ra_events.invoke({
        "location": "athens",
        "start_date": "2025-11-15",
        "end_date": "2025-11-15",
        "days_ahead": 1
    })

    print(result)
    print("\n" + "="*80)
    print("Checking if addresses are included...")
    print("="*80 + "\n")

    # Check if the result includes addresses (look for street names or numbers)
    if "Iraklidon" in result or "Pl. Theatrou" in result or any(char.isdigit() for line in result.split('\n') if '📍' in line for char in line):
        print("✅ SUCCESS: Venue addresses are being returned!")
        print("\nExample venues with addresses:")
        for line in result.split('\n'):
            if '📍' in line and any(c.isdigit() for c in line):
                print(f"  {line.strip()}")
    else:
        print("⚠️ WARNING: No full addresses detected in results")
        print("Venue names only (expected format before fix):")
        for line in result.split('\n'):
            if '📍' in line:
                print(f"  {line.strip()}")

if __name__ == "__main__":
    test_ra_scraper()
