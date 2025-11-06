"""
Routing functions for LangGraph conditional edges
"""
from typing import Dict, Any
from langchain_core.messages import ToolMessage
import logging

from backend.services.graph_schemas import AgentState
from backend.services.tool_parsers import parse_tool_messages

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

        # Otherwise, do data source routing
        location = "athens"

        # CASE 1: If dates provided, check if CSV has data for those dates
        if start_date and end_date:
            events_exist = self.vector_store.check_events_exist(start_date, end_date, location)
            if events_exist:
                logger.info("📊 Routing: CSV has data → CSVRetrieval")
                return "csv"
            else:
                logger.info("🌐 Routing: No CSV data → WebAgent")
                return "web"

        # CASE 2: No dates - try CSV if it has ANY events
        if self.vector_store.events_df is not None and len(self.vector_store.events_df) > 0:
            logger.info("📊 Routing: No dates, but CSV has events → CSVRetrieval")
            return "csv"

        logger.info("🌐 Routing: CSV empty → WebAgent")
        return "web"

    def route_after_location(self, state: AgentState) -> str:
        """Route to data source after getting location"""
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        location = "athens"

        # Same logic as route_completeness_check
        if start_date and end_date:
            events_exist = self.vector_store.check_events_exist(start_date, end_date, location)
            if events_exist:
                logger.info("📊 Routing after location: CSV has data → CSVRetrieval")
                return "csv"
            else:
                logger.info("🌐 Routing after location: No CSV data → WebAgent")
                return "web"

        if self.vector_store.events_df is not None and len(self.vector_store.events_df) > 0:
            logger.info("📊 Routing after location: CSV has events → CSVRetrieval")
            return "csv"

        logger.info("🌐 Routing after location: CSV empty → WebAgent")
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
        """Check if RA/GO-OUT tools found events, fallback to Tavily if not"""
        messages = state.get("messages", [])
        tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]

        if tool_messages:
            # Quick check: parse tool messages to see if events were found
            events = parse_tool_messages(tool_messages, "")
            events_count = len(events)

            if events_count > 0:
                logger.info(f"✅ RA/GO-OUT found {events_count} events → StoreEvents")
                return "store"
            else:
                logger.info("⚠️ RA/GO-OUT found 0 events → WebSearchAgent (Tavily fallback)")
                return "websearch"

        return "store"
