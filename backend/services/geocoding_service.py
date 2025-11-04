"""
Geocoding Service - Convert venue addresses to coordinates and calculate distances
Uses Nominatim (OpenStreetMap) - FREE, no API key required
Fallback to Tavily web search for failed geocoding attempts
"""

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from typing import Optional, Tuple, Dict, Any
import logging
import time
import hashlib
import re
import os
import requests

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
        # Tavily API key for fallback geocoding
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")

    def _rate_limit(self):
        """Enforce rate limiting for Nominatim API"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit_seconds:
            sleep_time = self.rate_limit_seconds - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _geocode_with_tavily(self, venue_address: str) -> Optional[Tuple[float, float]]:
        """
        Fallback geocoding using Tavily web search
        Uses comprehensive search to minimize API calls

        Args:
            venue_address: Venue name/address

        Returns:
            Tuple of (latitude, longitude) or None if extraction fails
        """
        if not self.tavily_api_key:
            logger.warning("⚠️ Tavily API key not configured - skipping fallback geocoding")
            return None

        try:
            from backend.tools.tavily_search import get_tavily_search_tool

            # Comprehensive search query (targets Google Maps, venue websites, review sites)
            search_query = f"{venue_address} Athens Greece google maps coordinates location address"
            logger.info(f"🌐 Tavily fallback: searching for '{venue_address}'")

            # Execute Tavily search with more results for better coverage
            tavily_tool = get_tavily_search_tool(max_results=5)
            results = tavily_tool.invoke({"query": search_query})

            # Parse results to extract coordinates
            coords = self._extract_coords_from_tavily(results, venue_address)

            if coords:
                logger.info(f"✅ Tavily found coordinates for '{venue_address}': {coords}")
                return coords
            else:
                logger.warning(f"⚠️ Tavily could not find coordinates for '{venue_address}'")
                return None

        except Exception as e:
            logger.error(f"❌ Error in Tavily fallback geocoding: {e}")
            return None

    def _extract_coords_from_google_maps_url(self, url: str) -> Optional[Tuple[float, float]]:
        """
        Extract coordinates from Google Maps URLs

        Handles formats like:
        - https://www.google.com/maps/place/.../@37.9776,23.7220,15z
        - https://www.google.com/maps?q=37.9776,23.7220
        - https://maps.google.com/?ll=37.9776,23.7220

        Args:
            url: Google Maps URL

        Returns:
            Tuple of (latitude, longitude) or None
        """
        try:
            # Pattern 1: /@lat,lon,zoom format
            match = re.search(r'/@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+),\d+z', url)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                if 37.8 <= lat <= 38.2 and 23.5 <= lon <= 24.0:
                    return (lat, lon)

            # Pattern 2: ?q=lat,lon format
            match = re.search(r'[?&]q=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)', url)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                if 37.8 <= lat <= 38.2 and 23.5 <= lon <= 24.0:
                    return (lat, lon)

            # Pattern 3: ll=lat,lon format
            match = re.search(r'[?&]ll=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)', url)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                if 37.8 <= lat <= 38.2 and 23.5 <= lon <= 24.0:
                    return (lat, lon)

            return None

        except Exception as e:
            logger.debug(f"Error extracting from Google Maps URL: {e}")
            return None

    def _extract_coords_from_tavily(self, results: Any, venue_name: str) -> Optional[Tuple[float, float]]:
        """
        Extract latitude/longitude from Tavily search results

        Looks for patterns like:
        - Google Maps URLs with embedded coordinates
        - "37.9776671, 23.7220567"
        - "lat: 37.977, lon: 23.722"
        - "37.977°N 23.722°E"

        Args:
            results: Tavily search results (string or list)
            venue_name: Name of venue for logging

        Returns:
            Tuple of (latitude, longitude) or None
        """
        try:
            # Convert results to string and collect URLs
            results_text = ""
            urls = []

            if isinstance(results, list):
                # Extract both content and URLs from Tavily results
                for r in results:
                    if isinstance(r, dict):
                        url = r.get('url', '')
                        if 'google.com/maps' in url or 'maps.google.com' in url:
                            urls.append(url)
                        results_text += f" {r.get('content', '')} {url} {r.get('title', '')}"
                    else:
                        results_text += f" {str(r)}"
                logger.debug(f"Tavily returned {len(results)} results for '{venue_name}'")
            else:
                results_text = str(results)

            # PRIORITY 1: Try extracting from Google Maps URLs first (most reliable)
            for url in urls:
                coords = self._extract_coords_from_google_maps_url(url)
                if coords:
                    logger.info(f"✅ Tavily found coordinates for '{venue_name}' from Google Maps URL: {coords}")
                    return coords

            # PRIORITY 2: Try text-based coordinate patterns
            patterns = [
                # Pattern 1: Google Maps URL format "@37.9776,23.7220,15z" (in text)
                r'@(\d{2}\.\d{4,}),(\d{2}\.\d{4,})',
                # Pattern 2: "lat: 37.977, lon: 23.722" or "latitude: 37.977, longitude: 23.722"
                r'lat(?:itude)?[:\s]+(\d{2}\.\d{4,})[,\s]+lon(?:gitude)?[:\s]+(\d{2}\.\d{4,})',
                # Pattern 3: "37.977°N 23.722°E" or "37.977° N, 23.722° E"
                r'(\d{2}\.\d{4,})\s*°?\s*N[,\s]+(\d{2}\.\d{4,})\s*°?\s*E',
                # Pattern 4: Plain coordinates "37.9776671, 23.7220567"
                r'(\d{2}\.\d{4,})\s*,\s*(\d{2}\.\d{4,})',
            ]

            for idx, pattern in enumerate(patterns, 1):
                match = re.search(pattern, results_text, re.IGNORECASE)
                if match:
                    try:
                        lat, lon = float(match.group(1)), float(match.group(2))

                        # Validate coordinates are in Athens area (roughly)
                        # Athens: lat ~37.8-38.2, lon ~23.5-24.0
                        if 37.8 <= lat <= 38.2 and 23.5 <= lon <= 24.0:
                            logger.info(f"✅ Tavily found coordinates for '{venue_name}': ({lat}, {lon}) using pattern {idx}")
                            return (lat, lon)
                        else:
                            logger.debug(f"Found coordinates ({lat}, {lon}) but outside Athens area (pattern {idx})")
                            continue  # Try next pattern
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse coordinates with pattern {idx}: {e}")
                        continue

            # Log sample of search results for debugging
            sample = results_text[:200] if len(results_text) > 200 else results_text
            logger.warning(f"⚠️ Could not extract valid Athens coordinates for '{venue_name}'. Sample: {sample}...")
            return None

        except Exception as e:
            logger.error(f"❌ Error extracting coordinates from Tavily results: {e}")
            return None

    def geocode_venue(self, venue_address: str, use_tavily_fallback: bool = True) -> Optional[Tuple[float, float]]:
        """
        Convert venue address to coordinates (latitude, longitude)
        Uses Nominatim (OpenStreetMap) with optional Tavily fallback

        Args:
            venue_address: Full venue address (can include venue name)
            use_tavily_fallback: If True, use Tavily when Nominatim fails

        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        # Check cache first
        cache_key = venue_address.lower().strip()
        if cache_key in self.geocode_cache:
            logger.debug(f"Cache hit for venue: {venue_address}")
            return self.geocode_cache[cache_key]

        # Try multiple search strategies with Nominatim
        search_strategies = []

        # Strategy 1: If address contains comma, try the address part only (after first comma)
        if ',' in venue_address:
            address_only = ','.join(venue_address.split(',')[1:]).strip()
            if address_only:
                search_strategies.append(f"{address_only}, Athens, Greece")

        # Strategy 2: Original address with Athens, Greece appended
        if "athens" not in venue_address.lower():
            search_strategies.append(f"{venue_address}, Athens, Greece")
        else:
            search_strategies.append(venue_address)

        # Strategy 3: Just the venue address as-is (if different from strategy 2)
        if venue_address not in search_strategies:
            search_strategies.append(venue_address)

        # Try each strategy
        for idx, search_query in enumerate(search_strategies, 1):
            try:
                # Rate limiting
                self._rate_limit()

                # Geocode the address
                logger.debug(f"Nominatim attempt {idx}/{len(search_strategies)}: {search_query}")
                location = self.geolocator.geocode(search_query, timeout=10)

                if location:
                    coords = (location.latitude, location.longitude)
                    self.geocode_cache[cache_key] = coords
                    logger.info(f"✅ Geocoded '{venue_address}' → {coords} (strategy {idx})")
                    return coords

            except Exception as e:
                logger.debug(f"Strategy {idx} failed: {e}")
                continue

        # All Nominatim strategies failed
        logger.warning(f"⚠️ Nominatim could not geocode venue: {venue_address}")

        # Try Tavily fallback if enabled
        if use_tavily_fallback:
            logger.info(f"🌐 Attempting Tavily fallback for '{venue_address}'")
            coords = self._geocode_with_tavily(venue_address)
            if coords:
                # Cache the result
                self.geocode_cache[cache_key] = coords
                return coords

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
