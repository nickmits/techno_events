"""
Test if RA.co GraphQL API returns venue coordinates directly
"""
import sys
import requests
import json

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# GraphQL query to check what venue fields are available
graphql_query = """
query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $pageSize: Int) {
  eventListings(filters: $filters, pageSize: $pageSize) {
    data {
      event {
        title
        date
        venue {
          id
          name
          address
          live
          latitude
          longitude
          area {
            name
            urlName
          }
        }
      }
    }
  }
}
"""

variables = {
    "filters": {
        "areas": {"eq": 37},  # Athens
        "listingDate": {
            "gte": "2025-11-15",
            "lte": "2025-11-16"
        }
    },
    "pageSize": 5
}

headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

print("="*80)
print("Testing if RA.co API provides venue coordinates")
print("="*80 + "\n")

try:
    response = requests.post(
        "https://ra.co/graphql",
        json={"query": graphql_query, "variables": variables},
        headers=headers,
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()

        if "errors" in data:
            print("❌ GraphQL errors:")
            print(json.dumps(data["errors"], indent=2))
        else:
            events = data.get("data", {}).get("eventListings", {}).get("data", [])

            if events:
                print(f"Found {len(events)} events. Checking for coordinates...\n")

                coords_found = 0
                for listing in events:
                    event = listing.get("event", {})
                    venue = event.get("venue", {})

                    title = event.get("title", "Unknown")
                    venue_name = venue.get("name", "Unknown")
                    lat = venue.get("latitude")
                    lon = venue.get("longitude")
                    address = venue.get("address", "No address")

                    print(f"Event: {title}")
                    print(f"  Venue: {venue_name}")
                    print(f"  Address: {address}")

                    if lat and lon:
                        print(f"  ✅ Coordinates: ({lat}, {lon})")
                        print(f"  Google Maps: https://www.google.com/maps?q={lat},{lon}")
                        coords_found += 1
                    else:
                        print(f"  ❌ No coordinates in API")
                    print()

                print("="*80)
                print(f"Result: {coords_found}/{len(events)} venues have coordinates in RA API")
                print("="*80)

                if coords_found > 0:
                    print("\n✅ SOLUTION FOUND: RA.co API provides coordinates!")
                    print("We should use these directly instead of geocoding!")
                else:
                    print("\n❌ RA.co API does NOT provide coordinates")
                    print("We need to rely on geocoding services")
            else:
                print("No events found")
    else:
        print(f"HTTP Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")
