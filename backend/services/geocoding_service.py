"""
Geocoding Service - Convert venue addresses to coordinates and calculate distances
Uses Nominatim (OpenStreetMap) - FREE, no API key required
"""

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from typing import Optional, Tuple, Dict, Any
import logging
import time
import hashlib

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding venue addresses and calculating distances"""

    def __init__(self):
        """Initialize Nominatim geocoder with rate limiting"""
        # User agent is required by Nominatim
        self.geolocator = Nominatim(user_agent="techno_events_athens")
        # Cache to avoid repeated geocoding calls
        self.geocode_cache: Dict[str, Tuple[float, float]] = {}
        # Rate limiting: 1 request per second for Nominatim
        self.last_request_time = 0
        self.rate_limit_seconds = 1.0

    def _rate_limit(self):
        """Enforce rate limiting for Nominatim API"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit_seconds:
            sleep_time = self.rate_limit_seconds - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def geocode_venue(self, venue_address: str) -> Optional[Tuple[float, float]]:
        """
        Convert venue address to coordinates (latitude, longitude)

        Args:
            venue_address: Full venue address

        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        # Check cache first
        cache_key = venue_address.lower().strip()
        if cache_key in self.geocode_cache:
            logger.debug(f"Cache hit for venue: {venue_address}")
            return self.geocode_cache[cache_key]

        try:
            # Add "Athens, Greece" to improve accuracy
            search_query = f"{venue_address}, Athens, Greece"

            # Rate limiting
            self._rate_limit()

            # Geocode the address
            logger.info(f"Geocoding venue: {search_query}")
            location = self.geolocator.geocode(search_query, timeout=10)

            if location:
                coords = (location.latitude, location.longitude)
                self.geocode_cache[cache_key] = coords
                logger.info(f"✅ Geocoded '{venue_address}' → {coords}")
                return coords
            else:
                logger.warning(f"⚠️ Could not geocode venue: {venue_address}")
                return None

        except Exception as e:
            logger.error(f"❌ Error geocoding venue '{venue_address}': {e}")
            return None

    def calculate_distance(
        self,
        user_coords: Tuple[float, float],
        venue_coords: Tuple[float, float]
    ) -> Optional[float]:
        """
        Calculate distance between user and venue in kilometers

        Args:
            user_coords: (latitude, longitude) of user
            venue_coords: (latitude, longitude) of venue

        Returns:
            Distance in kilometers or None if calculation fails
        """
        try:
            distance = geodesic(user_coords, venue_coords).kilometers
            return round(distance, 2)
        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return None  # Return None if calculation fails

    def estimate_travel_times(self, distance_km: float) -> tuple[int, int]:
        """
        Estimate driving and walking times based on distance

        Uses realistic Athens city center speeds:
        - Walking: 5 km/h average
        - Driving: 25 km/h average (Athens traffic is heavy!)

        Args:
            distance_km: Distance in kilometers

        Returns:
            Tuple of (drive_time_minutes, walk_time_minutes)
        """
        # Average speeds in Athens
        WALK_SPEED_KMH = 5.0   # Average walking speed
        DRIVE_SPEED_KMH = 25.0  # Athens city traffic (realistic!)

        # Calculate times in minutes
        walk_time_min = int((distance_km / WALK_SPEED_KMH) * 60)
        drive_time_min = int((distance_km / DRIVE_SPEED_KMH) * 60)

        return drive_time_min, walk_time_min

    def add_distance_to_event(
        self,
        event: Dict[str, Any],
        user_coords: Tuple[float, float]
    ) -> Dict[str, Any]:
        """
        Add distance and travel time information to an event dictionary

        Args:
            event: Event dictionary with venue information
            user_coords: User's (latitude, longitude)

        Returns:
            Event dictionary with added distance_km, drive_time_min, walk_time_min, venue_lat/venue_lon fields
        """
        venue_address = event.get("venue", "")

        if not venue_address or venue_address == "TBA":
            event["distance_km"] = None
            event["venue_lat"] = None
            event["venue_lon"] = None
            event["drive_time_min"] = None
            event["walk_time_min"] = None
            return event

        # Check if event already has coordinates
        venue_lat = event.get("venue_lat")
        venue_lon = event.get("venue_lon")

        if venue_lat and venue_lon:
            # Use existing coordinates
            try:
                venue_coords = (float(venue_lat), float(venue_lon))
            except (ValueError, TypeError):
                # Geocode if coordinates are invalid
                venue_coords = self.geocode_venue(venue_address)
        else:
            # Geocode the venue
            venue_coords = self.geocode_venue(venue_address)

        if venue_coords:
            # Calculate distance
            distance = self.calculate_distance(user_coords, venue_coords)
            event["distance_km"] = distance
            event["venue_lat"] = venue_coords[0]
            event["venue_lon"] = venue_coords[1]

            # Calculate travel times
            if distance is not None:
                drive_time, walk_time = self.estimate_travel_times(distance)
                event["drive_time_min"] = drive_time
                event["walk_time_min"] = walk_time
            else:
                event["drive_time_min"] = None
                event["walk_time_min"] = None
        else:
            # Could not geocode
            event["distance_km"] = None
            event["venue_lat"] = None
            event["venue_lon"] = None
            event["drive_time_min"] = None
            event["walk_time_min"] = None

        return event

    def sort_events_by_distance(
        self,
        events: list[Dict[str, Any]],
        user_coords: Tuple[float, float]
    ) -> list[Dict[str, Any]]:
        """
        Sort events by distance from user (closest first)

        Args:
            events: List of event dictionaries
            user_coords: User's (latitude, longitude)

        Returns:
            Sorted list of events with distance_km added
        """
        if not events:
            return []

        logger.info(f"Sorting {len(events)} events by distance from user location {user_coords}")

        # Add distance to each event
        events_with_distance = []
        for event in events:
            event_with_distance = self.add_distance_to_event(event, user_coords)
            events_with_distance.append(event_with_distance)

        # Sort by distance (closest first, None values at the end)
        sorted_events = sorted(
            events_with_distance,
            key=lambda e: (e.get("distance_km") is None, e.get("distance_km") or float('inf'))
        )

        # Log the closest event with valid distance
        closest_distance = next((e.get('distance_km') for e in sorted_events if e.get('distance_km') is not None), 'N/A')
        logger.info(f"✅ Sorted events by distance: closest = {closest_distance} km")

        return sorted_events
