"""
Events Service - Integrates LangGraph multi-agent system for event discovery
"""

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from dotenv import load_dotenv
import operator
import os
import logging

from backend.tools.ra_events import fetch_ra_events
from backend.tools.goout_events import fetch_goout_events

load_dotenv()

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State shared between agents"""
    messages: Annotated[List[BaseMessage], operator.add]
    next: str


class EventsService:
    """Service for managing event queries through LangGraph"""

    def __init__(self):
        """Initialize the service and build the LangGraph"""
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.model = ChatOpenAI(model="gpt-4o-mini")
        self.graph = None
        logger.info("EventsService initialized")

    async def _build_graph(self):
        """Build the multi-agent graph with RA and GO-OUT agents"""

        # Build graph: Query → RA → GO-OUT → END (sequential execution)
        graph = StateGraph(AgentState)

        graph.add_node("RAEvents", self._ra_agent_node)
        graph.add_node("GOOUTEvents", self._goout_agent_node)

        # Set entry point and create sequential chain
        graph.set_entry_point("RAEvents")
        graph.add_edge("RAEvents", "GOOUTEvents")
        graph.add_edge("GOOUTEvents", END)

        return graph.compile()

    def _ra_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """RA Events agent node - fetches events from Resident Advisor"""
        messages = state["messages"]

        # Get the user query
        user_message = messages[0].content if messages else ""

        # Create model with tool binding
        model_with_tools = self.model.bind_tools([fetch_ra_events])

        # System prompt
        system_msg = """You are a Resident Advisor events specialist. Fetch electronic music events using fetch_ra_events.

        Supported locations: greece, athens, berlin, london, newyork, amsterdam

        Always use custom date ranges if the user specifies dates:
        - Use start_date and end_date parameters in YYYY-MM-DD format
        - Examples: "events Nov 1-5" → start_date="2025-11-01", end_date="2025-11-05"

        Call the fetch_ra_events tool with appropriate parameters based on the user's query."""

        # Invoke model
        response = model_with_tools.invoke([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_message}
        ])

        # Check if tool was called
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_call = response.tool_calls[0]
            # Execute the tool
            result = fetch_ra_events.invoke(tool_call["args"])
        else:
            result = "Unable to fetch RA events - no valid query provided"

        return {
            "messages": [HumanMessage(content=result, name="RAEvents")]
        }

    def _goout_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """GO-OUT Events agent node - fetches events from GO-OUT"""
        messages = state["messages"]

        # Get the user query (first message)
        user_message = messages[0].content if messages else ""

        # Create model with tool binding
        model_with_tools = self.model.bind_tools([fetch_goout_events])

        # System prompt
        system_msg = """You are a GO-OUT events specialist. Fetch nightlife, concerts, and sports events using fetch_goout_events.

        Categories: nightlife, concerts, sports, all
        Location filtering: athens, amsterdam, paris, toronto, etc. (searches in address)

        Always use custom date ranges if the user specifies dates:
        - Use start_date and end_date parameters in YYYY-MM-DD format
        - Examples: "nightlife in Athens Nov 1-5" → category="nightlife", location="athens", start_date="2025-11-01", end_date="2025-11-05"

        Call the fetch_goout_events tool with appropriate parameters based on the user's query."""

        # Invoke model
        response = model_with_tools.invoke([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_message}
        ])

        # Check if tool was called
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_call = response.tool_calls[0]
            # Execute the tool
            result = fetch_goout_events.invoke(tool_call["args"])
        else:
            result = "Unable to fetch GO-OUT events - no valid query provided"

        return {
            "messages": [HumanMessage(content=result, name="GOOUTEvents")]
        }

    async def fetch_events(
        self,
        query: str,
        location: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ahead: Optional[int] = 30
    ) -> Dict[str, Any]:
        """
        Fetch events using the LangGraph multi-agent system

        Args:
            query: Natural language query
            location: Optional location filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            days_ahead: Days ahead if dates not specified

        Returns:
            Dictionary containing messages from all agents
        """
        try:
            # Build graph if not already built
            if self.graph is None:
                logger.info("Building LangGraph...")
                self.graph = await self._build_graph()

            # Enhance query with filters if provided
            enhanced_query = query
            if location:
                enhanced_query += f" in {location}"
            if start_date and end_date:
                enhanced_query += f" between {start_date} and {end_date}"
            elif start_date:
                enhanced_query += f" starting from {start_date}"

            logger.info(f"Executing query: {enhanced_query}")

            # Execute query through graph
            result = await self.graph.ainvoke({
                "messages": [HumanMessage(content=enhanced_query)]
            })

            return result

        except Exception as e:
            logger.error(f"Error in fetch_events: {str(e)}")
            raise
