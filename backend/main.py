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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


# Request/Response Models
class EventsRequest(BaseModel):
    """Request model for fetching events"""
    query: str = Field(..., description="Natural language query for events", example="What events are happening in Athens this weekend?")
    location: Optional[str] = Field(None, description="Specific location filter", example="athens")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format", example="2025-11-01")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format", example="2025-11-05")
    days_ahead: Optional[int] = Field(30, description="Days ahead if dates not specified", ge=1, le=90)


class EventSource(BaseModel):
    """Individual event source response"""
    name: str = Field(..., description="Name of the agent/source")
    content: str = Field(..., description="Formatted event listings")


class EventsResponse(BaseModel):
    """Response model for events endpoint"""
    query: str = Field(..., description="Original query")
    sources: List[EventSource] = Field(..., description="Event data from different sources")
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
    Fetch events using LangGraph multi-agent system

    This endpoint queries both Resident Advisor and GO-OUT platforms
    using specialized agents for comprehensive event discovery.

    Args:
        request: EventsRequest with query and optional filters

    Returns:
        EventsResponse with combined results from all agents
    """
    try:
        logger.info(f"Processing events query: {request.query}")

        # Execute query through LangGraph
        result = await events_service.fetch_events(
            query=request.query,
            location=request.location,
            start_date=request.start_date,
            end_date=request.end_date,
            days_ahead=request.days_ahead
        )

        # Format response
        sources = [
            EventSource(name=msg.name, content=msg.content)
            for msg in result["messages"][1:]  # Skip initial user message
            if hasattr(msg, 'name')
        ]

        response = EventsResponse(
            query=request.query,
            sources=sources,
            total_sources=len(sources),
            timestamp=datetime.utcnow().isoformat()
        )

        logger.info(f"Successfully retrieved events from {len(sources)} sources")
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
