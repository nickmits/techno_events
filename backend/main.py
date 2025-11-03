"""
FastAPI backend for Techno Events
Provides endpoints for event discovery using LangGraph multi-agent system
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from backend.services.events_service import EventsService
from backend.services.geocoding_service import GeocodingService
import math

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_str(value) -> Optional[str]:
    """Convert value to string, handling NaN and None"""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
    return str(value) if value else None

# Initialize FastAPI app
app = FastAPI(
    title="Techno Events API",
    description="Multi-agent event discovery system powered by LangGraph",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
events_service = EventsService()
geocoding_service = GeocodingService()


# Request/Response Models
class EventsRequest(BaseModel):
    """Request model for fetching events - ATHENS ONLY"""
    query: str = Field(..., description="Natural language query for Athens events", example="What events are happening this weekend?")
    location: Optional[str] = Field(None, description="(Ignored - always Athens)", example="athens")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format", example="2025-11-01")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format", example="2025-11-05")
    days_ahead: Optional[int] = Field(30, description="Days ahead if dates not specified", ge=1, le=90)
    user_location: Optional[str] = Field(None, description="User's location as text (e.g., 'Syntagma Square', 'Monastiraki')", example="Syntagma Square")


class Event(BaseModel):
    """Individual event structure"""
    title: str = Field(..., description="Event title")
    venue: str = Field(..., description="Venue name")
    event_date: str = Field(..., description="Event date")
    url: str = Field(..., description="Event URL")
    source: str = Field(..., description="Event source (RA, GO-OUT, or CSV)")
    location: Optional[str] = Field(None, description="City/location")
    attending: Optional[str] = Field(None, description="Number attending")
    music_types: Optional[str] = Field(None, description="Music genres")
    distance_km: Optional[float] = Field(None, description="Distance from user in kilometers")
    drive_time_min: Optional[int] = Field(None, description="Estimated driving time in minutes")
    walk_time_min: Optional[int] = Field(None, description="Estimated walking time in minutes")
    venue_lat: Optional[float] = Field(None, description="Venue latitude")
    venue_lon: Optional[float] = Field(None, description="Venue longitude")


class EventSource(BaseModel):
    """Individual event source response"""
    name: str = Field(..., description="Name of the agent/source")
    content: str = Field(..., description="Formatted event listings")


class EventsResponse(BaseModel):
    """Response model for events endpoint"""
    query: str = Field(..., description="Original query")
    source: str = Field(..., description="Data source: 'csv' (cached), 'web' (RA/GO-OUT APIs), or 'web_search' (Tavily)")
    intro: Optional[str] = Field(None, description="Brief conversational introduction")
    events: List[Event] = Field(default_factory=list, description="Structured event list")
    sources: List[EventSource] = Field(default_factory=list, description="Event data from different sources")
    total_sources: int = Field(..., description="Number of sources queried")
    timestamp: str = Field(..., description="Query execution timestamp")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Techno Events API",
        "version": "1.0.0"
    }


@app.post("/api/events", response_model=EventsResponse)
async def fetch_events(request: EventsRequest):
    """
    Fetch Athens events using LangGraph multi-agent system

    ATHENS-ONLY: This endpoint only searches for events in Athens, Greece.
    Queries are intelligently routed to either cached CSV data or web APIs
    (Resident Advisor and GO-OUT) for Athens events.

    Args:
        request: EventsRequest with query and optional filters (location ignored)

    Returns:
        EventsResponse with conversational response about Athens events
    """
    try:
        logger.info(f"Processing events query: {request.query}")

        # Geocode user location if provided
        user_lat, user_lon = None, None
        if request.user_location:
            logger.info(f"Geocoding user location: {request.user_location}")
            user_coords = geocoding_service.geocode_venue(request.user_location)
            if user_coords:
                user_lat, user_lon = user_coords
                logger.info(f"✅ User location geocoded: {user_lat}, {user_lon}")
            else:
                logger.warning(f"⚠️ Could not geocode user location: {request.user_location}")

        # Execute query through LangGraph
        result = await events_service.fetch_events(
            query=request.query,
            location=request.location,
            start_date=request.start_date,
            end_date=request.end_date,
            days_ahead=request.days_ahead,
            user_lat=user_lat,
            user_lon=user_lon
        )

        # Extract data from result
        final_response = result.get("final_response", "")
        retrieved_events = result.get("retrieved_events", [])
        source_type = result.get("source", "unknown")

        logger.info(f"DEBUG: source_type = {source_type} (type: {type(source_type)})")

        # Build structured events list
        structured_events = []
        for event in retrieved_events:
            structured_events.append(Event(
                title=event.get("title", "Unknown Event"),
                venue=event.get("venue", "TBA"),
                event_date=event.get("event_date", "TBA"),
                url=event.get("url", ""),
                source=event.get("source", source_type),
                location=safe_str(event.get("location")),
                attending=safe_str(event.get("attending")),
                music_types=safe_str(event.get("music_types")),
                distance_km=event.get("distance_km"),
                drive_time_min=event.get("drive_time_min"),
                walk_time_min=event.get("walk_time_min"),
                venue_lat=event.get("venue_lat"),
                venue_lon=event.get("venue_lon")
            ))

        # Build sources list (for backwards compatibility)
        sources = []
        for msg in result["messages"][1:]:  # Skip initial user message
            if hasattr(msg, 'name') and hasattr(msg, 'content'):
                if msg.name in ["RAEvents", "GOOUTEvents"]:
                    sources.append(
                        EventSource(name=msg.name, content=msg.content)
                    )

        response = EventsResponse(
            query=request.query,
            source=source_type,  # "csv", "web", or "web_search"
            intro=final_response if final_response else None,
            events=structured_events,
            sources=sources,
            total_sources=len(sources) + (1 if final_response else 0),
            timestamp=datetime.utcnow().isoformat()
        )

        logger.info(f"Successfully generated conversational response with {len(sources)} sources")
        return response

    except Exception as e:
        logger.error(f"Error processing events request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch events: {str(e)}"
        )


@app.get("/api/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "events-api",
        "components": {
            "langgraph": "ready",
            "agents": ["RAEvents", "GOOUTEvents"]
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
