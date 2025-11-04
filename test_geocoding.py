"""
Test script to verify geocoding with Tavily fallback
"""
import sys
import os
import logging
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.geocoding_service import GeocodingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_geocoding():
    """Test geocoding with various venue types"""

    print("\n" + "="*80)
    print("GEOCODING SERVICE TEST")
    print("="*80 + "\n")

    # Initialize service
    service = GeocodingService()

    # Check Tavily API key
    if service.tavily_api_key:
        print("✅ Tavily API key configured")
    else:
        print("⚠️  Tavily API key NOT configured - fallback won't work")

    print("\n")

    # Test venues (mix of easy and hard cases)
    test_venues = [
        "Cantina Social",  # Should work with Nominatim
        "Burger Disco Club",  # Might fail with Nominatim
        "COZMO Athens, Leoforos Vouliagmenis",  # More specific address
        "TBA - Secret Location",  # Should skip (TBA)
        "Six D.O.G.S",  # Popular venue
    ]

    results = []

    for venue in test_venues:
        print(f"\n{'─'*80}")
        print(f"Testing: {venue}")
        print(f"{'─'*80}")

        if venue == "TBA - Secret Location":
            print("⏭️  Skipping TBA venue (expected behavior)")
            results.append((venue, None, "skipped"))
            continue

        coords = service.geocode_venue(venue, use_tavily_fallback=True)

        if coords:
            lat, lon = coords
            print(f"✅ SUCCESS: {venue}")
            print(f"   Coordinates: {lat}, {lon}")
            print(f"   Google Maps: https://www.google.com/maps?q={lat},{lon}")
            results.append((venue, coords, "success"))
        else:
            print(f"❌ FAILED: Could not geocode {venue}")
            results.append((venue, None, "failed"))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80 + "\n")

    success_count = sum(1 for _, _, status in results if status == "success")
    failed_count = sum(1 for _, _, status in results if status == "failed")
    skipped_count = sum(1 for _, _, status in results if status == "skipped")

    print(f"✅ Successful: {success_count}/{len(test_venues)}")
    print(f"❌ Failed: {failed_count}/{len(test_venues)}")
    print(f"⏭️  Skipped: {skipped_count}/{len(test_venues)}")

    if failed_count > 0:
        print("\nFailed venues:")
        for venue, _, status in results:
            if status == "failed":
                print(f"  - {venue}")

    print("\n" + "="*80 + "\n")

    # Test distance calculation
    if success_count > 0:
        print("\nTesting distance calculation...")
        # Use Syntagma Square as user location
        user_coords = (37.9755, 23.7348)
        print(f"User location: Syntagma Square {user_coords}")

        for venue, coords, status in results:
            if status == "success" and coords:
                distance = service.calculate_distance(user_coords, coords)
                if distance:
                    drive_time, walk_time = service.estimate_travel_times(distance)
                    print(f"\n{venue}:")
                    print(f"  Distance: {distance} km")
                    print(f"  Drive time: {drive_time} min")
                    print(f"  Walk time: {walk_time} min")

if __name__ == "__main__":
    test_geocoding()
