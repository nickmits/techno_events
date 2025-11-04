"""
Test geocoding for the specific venues from the screenshot
"""
import sys
import os
from dotenv import load_dotenv
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.geocoding_service import GeocodingService

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

def test_screenshot_venues():
    """Test the exact venues from the screenshot"""

    print("="*80)
    print("Testing Venues from Screenshot")
    print("="*80 + "\n")

    service = GeocodingService()

    # Venues from the screenshot (using the full addresses shown in RA)
    test_venues = [
        ("SMUT Athens", "SMUT Athens, Vatsaxi 4, Athina 104 38, Greece, Athens"),
        ("Astron Club", "Astron Club, 121 Konstantinoupoleos St., Athens 104 47, Greece, Athens"),
        ("Temple Athens", "Temple Athens, Iakhou 17, 118 54 Athens, Greece, Athens"),
        ("The Host Thessaloniki", "The Host, Paikou 4, Thessaloniki, 54625, Greece, Thessaloniki"),
        ("Booze Cooperative", "Booze Cooperative, Kolokotroni 57 (Monastiraki Station) Athens 114, Athens"),
        ("Mercado Bar", "Mercado Bar, Merkos & Κρασσοπτερου Pyrgos, Ilia, Greece, Ali"),
    ]

    success_count = 0

    for name, address in test_venues:
        print(f"\n{'─'*80}")
        print(f"Venue: {name}")
        print(f"Address: {address}")
        print(f"{'─'*80}")

        coords = service.geocode_venue(address, use_tavily_fallback=True)

        if coords:
            lat, lon = coords
            print(f"✅ SUCCESS: ({lat}, {lon})")
            print(f"   Google Maps: https://www.google.com/maps?q={lat},{lon}")
            success_count += 1
        else:
            print(f"❌ FAILED: Could not geocode")
            print(f"   Reason: Neither Nominatim nor Tavily could find coordinates")
            print(f"   Possible fixes:")
            print(f"     1. Try searching manually: https://www.google.com/maps/search/{address.replace(' ', '+')}")
            print(f"     2. Address might need Greek characters")
            print(f"     3. Venue might be unlisted/new")

    print(f"\n{'='*80}")
    print(f"Results: {success_count}/{len(test_venues)} venues geocoded successfully")
    print(f"{'='*80}")

if __name__ == "__main__":
    test_screenshot_venues()
