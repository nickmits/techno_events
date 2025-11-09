"""
Routing functions for LangGraph conditional edges
"""
from typing import Dict, Any
from langchain_core.messages import ToolMessage
import logging

from services.graph_schemas import AgentState
from services.tool_parsers import parse_tool_messages

logger = logging.getLogger(__name__)


class GraphRouting:
    """Collection of routing functions for conditional edges"""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    def route_completeness_check(self, state: AgentState) -> str:
        """Check if we need to ask for location, or route to data source"""
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        user_lat = state.get("user_lat")
        user_lon = state.get("user_lon")

        # If we have dates but no user location, ask for it
        if (start_date or end_date) and (user_lat is None or user_lon is None):
            logger.info("📍 Have dates but no location → AskForLocation")
            return "ask_location"

        # Always fetch fresh events from web (RA/GO-OUT)
        # StoreEvents will merge with CSV and add only new events
        logger.info("🌐 Routing: Always fetch from web to get latest events")
        return "web"

    def route_after_location(self, state: AgentState) -> str:
        """Route to data source after getting location"""
        # Always fetch fresh events from web (RA/GO-OUT)
        # StoreEvents will merge with CSV and add only new events
        logger.info("🌐 Routing after location: Always fetch from web to get latest events")
        return "web"

    def route_csv_results(self, state: AgentState) -> str:
        """Check if CSV returned events"""
        events_count = state.get("events_count", 0)
        if events_count > 0:
            return "sort"
        return "web"  # Fallback to web if CSV empty

    def route_web_agent(self, state: AgentState) -> str:
        """Check if WebAgent called tools"""
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return "response"

    def route_tool_results(self, state: AgentState) -> str:
        """
        NOTE: This function is no longer used since CallTools now has a direct edge to StoreEvents.
        Kept for backwards compatibility but can be removed.
        """
        return "store"
