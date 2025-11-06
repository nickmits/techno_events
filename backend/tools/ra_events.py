"""
Resident Advisor Events Tool
Fetches electronic music events from RA using their GraphQL API
"""

from langchain_core.tools import tool
from datetime import datetime, timedelta
import requests


# Common area IDs for RA.co GraphQL API
AREA_IDS = {
    "greece": 37,      # Greece (Athens area)
    "athens": 37,      # Athens, Greece
    "berlin": 34,      # Berlin, Germany
    "london": 13,      # London, UK
    "newyork": 6,      # New York, USA
    "amsterdam": 29,   # Amsterdam, Netherlands
}


@tool
def fetch_ra_events(location: str = "greece", start_date: str = None, end_date: str = None, days_ahead: int = 30) -> str:
    """
    Fetch real electronic music event data from Resident Advisor using their GraphQL API.

    Args:
        location: Location name (e.g., 'greece', 'athens', 'berlin', 'london', 'newyork')
        start_date: Event start date in YYYY-MM-DD format (optional, defaults to today)
        end_date: Event end date in YYYY-MM-DD format (optional, defaults to start_date + days_ahead)
        days_ahead: Number of days ahead if start_date/end_date not provided (default: 30)

    Returns:
        Formatted string with actual event listings including titles, dates, venues, and URLs
    """
    try:
        # Get area ID
        area_id = AREA_IDS.get(location.lower())
        if not area_id:
            return f"❌ Unknown location: {location}. Available: {', '.join(AREA_IDS.keys())}"

        # Parse date range
        if start_date is None:
            event_start = datetime.now().strftime("%Y-%m-%d")
        else:
            event_start = start_date

        if end_date is None:
            event_end = (datetime.strptime(event_start, "%Y-%m-%d") + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        else:
            event_end = end_date

        # For listingDate filter: fetch events listed in wider window
        listing_start = datetime.now().strftime("%Y-%m-%d")
        listing_end = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

        # GraphQL query
        graphql_query = """
        query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int) {
          eventListings(filters: $filters, filterOptions: $filterOptions, page: $page, pageSize: $pageSize) {
            data {
              id
              listingDate
              event {
                id
                title
                date
                startTime
                endTime
                contentUrl
                flyerFront
                attending
                venue {
                  id
                  name
                  contentUrl
                  address
                  area {
                    name
                    country {
                      name
                    }
                  }
                }
              }
            }
            totalResults
          }
        }
        """

        # Variables
        variables = {
            "filters": {
                "areas": {"eq": area_id},
                "listingDate": {
                    "gte": listing_start,
                    "lte": listing_end
                }
            },
            "filterOptions": {"genre": True},
            "pageSize": 100,
            "page": 1
        }

        # Make request
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.post(
            "https://ra.co/graphql",
            json={"query": graphql_query, "variables": variables},
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return f"❌ API request failed with status {response.status_code}"

        data = response.json()

        # Parse results
        if "errors" in data:
            return f"❌ GraphQL errors: {data['errors']}"

        all_events = data.get("data", {}).get("eventListings", {}).get("data", [])

        # Filter events by actual event date (not listing date)
        filtered_events = []
        for listing in all_events:
            event = listing.get("event", {})
            event_date_str = event.get("date", "")[:10]  # Get YYYY-MM-DD

            # Check if event date is within requested range
            if event_start <= event_date_str <= event_end:
                filtered_events.append(listing)

        if not filtered_events:
            return f"❌ No events found in {location} between {event_start} and {event_end}."

        # Format output
        result = f"🎵 Events in {location.title()} ({len(filtered_events)} events found)\n"
        result += f"📅 Date range: {event_start} to {event_end}\n\n"

        for idx, listing in enumerate(filtered_events, 1):
            event = listing.get("event", {})
            title = event.get("title", "Untitled")
            date = event.get("date", "TBA")
            start_time = event.get("startTime", "")
            venue_info = event.get("venue", {})
            venue_name = venue_info.get("name", "Unknown Venue")
            venue_address = venue_info.get("address", "")
            venue_area = venue_info.get("area", {})
            area_name = venue_area.get("name", "") if venue_area else ""

            # Build full venue string: "Venue Name, Address, City" or just "Venue Name" if no address
            if venue_address and area_name:
                full_venue = f"{venue_name}, {venue_address}, {area_name}"
            elif venue_address:
                full_venue = f"{venue_name}, {venue_address}"
            else:
                full_venue = venue_name

            event_url = f"https://ra.co{event.get('contentUrl', '')}"
            attending = event.get("attending", 0)

            result += f"{idx}. {title}\n"
            result += f"   📍 {full_venue}\n"
            result += f"   📅 {date[:10]}"  # Just the date part
            if start_time:
                result += f" at {start_time[11:16]}"  # Extract time HH:MM
            result += f"\n"
            result += f"   👥 {attending} attending\n"
            result += f"   🔗 {event_url}\n\n"

        result += f"\n✅ Found {len(filtered_events)} events. Visit ra.co for complete details."
        return result

    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"
    except Exception as e:
        return f"❌ Error fetching RA events: {str(e)}"
