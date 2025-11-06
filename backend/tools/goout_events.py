"""
GO-OUT Events Tool
Fetches nightlife, concerts, and sports events from GO-OUT.co API
"""

from langchain_core.tools import tool
from datetime import datetime, timedelta
import requests


@tool
def fetch_goout_events(category: str = "nightlife", location: str = None, start_date: str = None, end_date: str = None, days_ahead: int = 30) -> str:
    """
    Fetch nightlife, concerts, and sports events from GO-OUT.co API.

    Args:
        category: Event category (nightlife, concerts, sports, all)
        location: Location filter (e.g., 'athens', 'amsterdam', 'paris') - filters by city name in address
        start_date: Event start date in YYYY-MM-DD format (optional, defaults to today)
        end_date: Event end date in YYYY-MM-DD format (optional, defaults to start_date + days_ahead)
        days_ahead: Number of days ahead if start_date/end_date not provided (default: 30)

    Returns:
        Formatted string with event listings including titles, dates, venues, music types, and URLs
    """
    try:
        # Parse date range
        if start_date is None:
            event_start = datetime.now()
        else:
            event_start = datetime.strptime(start_date, "%Y-%m-%d")

        if end_date is None:
            event_end = event_start + timedelta(days=days_ahead)
        else:
            event_end = datetime.strptime(end_date, "%Y-%m-%d")

        # Set end time to end of day to include all events on the last day
        event_end = event_end.replace(hour=23, minute=59, second=59)

        # API endpoint
        url = "https://www.go-out.co/endOne/getEventsByTypeNew?"

        # Request payload - Types mapping for different categories
        category_types = {
            "nightlife": ["אירועים", "מועדוני לילה"],  # Events + Nightclubs
            "concerts": ["קונצרטים"],  # Concerts
            "sports": ["ספורט"],  # Sports
            "all": ["אירועים", "מועדוני לילה", "קונצרטים", "ספורט"]
        }

        payload = {
            "skip": 0,
            "Types": category_types.get(category, ["אירועים", "מועדוני לילה"]),
            "limit": 100,
            "recivedDate": datetime.now().isoformat() + "Z",
            "location": {}
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://www.go-out.co/tickets/{category}",
            "Origin": "https://www.go-out.co"
        }

        # Make request
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code != 200:
            return f"❌ API request failed with status {response.status_code}"

        data = response.json()

        if not data.get('status'):
            return f"❌ API returned error status"

        all_events = data.get('events', [])

        if not all_events:
            return f"No events found for {category}"

        # Filter events by date
        filtered_events = []
        for event in all_events:
            try:
                event_date = datetime.fromisoformat(event['StartingDate'].replace('Z', ''))
                if event_start <= event_date <= event_end:
                    filtered_events.append(event)
            except:
                filtered_events.append(event)

        if not filtered_events:
            return f"No events found in {category} between {event_start.strftime('%Y-%m-%d')} and {event_end.strftime('%Y-%m-%d')}"

        # Filter by location if specified
        if location:
            # Map common city name variations (e.g., Athens -> Athina)
            location_variants = {
                'athens': ['athens', 'athina', 'αθήνα'],
                'thessaloniki': ['thessaloniki', 'θεσσαλονίκη', 'salonika'],
            }

            search_terms = location_variants.get(location.lower(), [location.lower()])

            location_filtered = []
            for event in filtered_events:
                address = event.get('EnglishAddress', '').lower()
                # Check if any of the search terms match
                if any(term in address for term in search_terms):
                    location_filtered.append(event)
            filtered_events = location_filtered

            if not filtered_events:
                return f"No events found in {location}"

        # Format output
        result = f"🎉 GO-OUT {category.title()} Events ({len(filtered_events)} events)\n"
        result += f"📅 Date range: {event_start.strftime('%Y-%m-%d')} to {event_end.strftime('%Y-%m-%d')}\n\n"

        for idx, event in enumerate(filtered_events[:20], 1):
            title = event.get('Title', 'Untitled')
            address = event.get('EnglishAddress', event.get('Adress', 'Address TBA'))

            try:
                start_dt = datetime.fromisoformat(event['StartingDate'].replace('Z', ''))
                date_str = start_dt.strftime('%Y-%m-%d at %H:%M')
            except:
                full_date = event.get('FullDate', {}).get('starting', {})
                date_info = full_date.get('date', {})
                time_info = full_date.get('time', {})
                date_str = f"{date_info.get('year', '')}-{date_info.get('month', '').zfill(2)}-{date_info.get('day', '').zfill(2)}"
                if time_info:
                    date_str += f" at {time_info.get('hours', '').zfill(2)}:{time_info.get('minutes', '').zfill(2)}"

            event_url = f"https://www.go-out.co/event/{event.get('Url', event.get('_id', ''))}"

            # Get music types (remove nulls)
            music_types = event.get('MusicType', [])
            music_types = [m for m in music_types if m] if music_types else []

            result += f"{idx}. {title}\n"
            result += f"   📍 {address}\n"
            result += f"   📅 {date_str}\n"
            if music_types:
                result += f"   🎵 {', '.join(music_types[:3])}\n"
            result += f"   🔗 {event_url}\n\n"

        result += f"\n✅ Found {len(filtered_events)} events. Visit go-out.co for complete details."
        return result

    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"
    except Exception as e:
        return f"❌ Error fetching GO-OUT events: {str(e)}"
