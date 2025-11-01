"""
Events Service - Integrates LangGraph multi-agent system for event discovery
"""

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from typing import TypedDict, Annotated, List, Optional, Dict, Any, Literal
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import operator
import os
import logging
import re

from backend.tools.ra_events import fetch_ra_events
from backend.tools.goout_events import fetch_goout_events
from backend.services.vector_store_service import VectorStoreService

load_dotenv()

logger = logging.getLogger(__name__)


class RouteDecision(BaseModel):
    """Schema for supervisor routing decision"""
    next: Literal["retrieve", "fetch"] = Field(
        description="The next action to take: 'retrieve' from cache or 'fetch' from web"
    )
    reasoning: str = Field(
        description="Brief explanation for the routing decision"
    )


def create_supervisor(llm: ChatOpenAI, system_prompt: str):
    """Create a supervisor chain for routing decisions using structured output"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        ("system", "Decide the next action: 'retrieve' from cache or 'fetch' from web. Provide your reasoning."),
    ])

    # Use with_structured_output for modern LangChain
    structured_llm = llm.with_structured_output(RouteDecision)

    return prompt | structured_llm


class AgentState(TypedDict):
    """State shared between agents"""
    messages: Annotated[List[BaseMessage], operator.add]
    next: str
    start_date: Optional[str]
    end_date: Optional[str]
    location: Optional[str]
    should_store: bool  # Whether to store fetched events


class EventsService:
    """Service for managing event queries through LangGraph"""

    def __init__(self):
        """Initialize the service and build the LangGraph"""
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.model = ChatOpenAI(model="gpt-4o-mini")
        self.graph = None
        self.vector_store = VectorStoreService()
        self.supervisor_chain = None  # Will be initialized in _build_graph
        logger.info("EventsService initialized with vector store")

    async def _build_graph(self):
        """Build the multi-agent graph with supervisor and conditional routing"""

        # Create supervisor chain
        self.supervisor_chain = create_supervisor(
            self.model,
            """You are a routing supervisor for an events discovery system.

Your job is to decide whether to:
- "retrieve" - Get events from the cached vector store (for previously fetched events or follow-up questions)
- "fetch" - Fetch fresh events from web APIs (Resident Advisor and GO-OUT)

RULES:
- If the user is asking for events for the first time, choose "fetch"
- If asking about previously fetched events or asking specific questions about existing events, choose "retrieve"
- If in doubt, choose "fetch" to ensure fresh data"""
        )

        # Build graph with supervisor routing
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("Supervisor", self._supervisor_node)
        graph.add_node("VectorRetrieval", self._retrieval_node)
        graph.add_node("WebFetch", self._web_fetch_node)
        graph.add_node("StoreEvents", self._storage_node)

        # Set entry point
        graph.set_entry_point("Supervisor")

        # Conditional routing from Supervisor
        graph.add_conditional_edges(
            "Supervisor",
            self._route_supervisor,
            {
                "retrieve": "VectorRetrieval",
                "fetch": "WebFetch"
            }
        )

        # After retrieval, go to END
        graph.add_edge("VectorRetrieval", END)

        # After web fetch, store events then END
        graph.add_edge("WebFetch", "StoreEvents")
        graph.add_edge("StoreEvents", END)

        return graph.compile()

    def _supervisor_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Supervisor node that decides whether to retrieve from vector store or fetch from web
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        # Extract date range from query or state
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        location = state.get("location")

        # Check if events exist in vector store for these dates
        events_exist = False
        if start_date and end_date:
            events_exist = self.vector_store.check_events_exist(start_date, end_date, location)
            logger.info(f"Vector store check: Events exist for {start_date} to {end_date}: {events_exist}")

        # Create context message for supervisor
        context_msg = f"""
Vector Store Status:
- Events exist for dates {start_date} to {end_date}: {events_exist}
- Location: {location or 'any'}

User Query: {user_query}

Decision Guide:
- Choose "fetch" if events_exist is False OR user requests different dates
- Choose "retrieve" if events_exist is True AND user is asking about those dates
- Choose "fetch" if uncertain
"""

        # Build messages for supervisor chain
        supervisor_messages = [
            HumanMessage(content=context_msg)
        ]

        # Invoke supervisor chain
        result = self.supervisor_chain.invoke({"messages": supervisor_messages})

        # Result is now a RouteDecision Pydantic model
        action = result.next if hasattr(result, 'next') else "fetch"
        reasoning = result.reasoning if hasattr(result, 'reasoning') else "No reasoning provided"

        logger.info(f"Supervisor decision: {action} - Reasoning: {reasoning}")

        return {
            "next": action,
            "messages": []
        }

    def _route_supervisor(self, state: AgentState) -> str:
        """Route based on supervisor decision"""
        return state.get("next", "fetch")

    def _retrieval_node(self, state: AgentState) -> Dict[str, Any]:
        """Retrieve events from vector store"""
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        logger.info(f"Retrieving events from vector store for query: {user_query}")

        # Query vector store
        result = self.vector_store.retrieve_events(user_query, k=20)

        return {
            "messages": [HumanMessage(content=result, name="VectorStore")]
        }

    def _web_fetch_node(self, state: AgentState) -> Dict[str, Any]:
        """Fetch events from RA and GO-OUT (sequential)"""
        messages = state["messages"]

        # Call RA agent
        ra_result = self._ra_agent_node(state)

        # Update state with RA result
        updated_state = {**state}
        updated_state["messages"] = state["messages"] + ra_result["messages"]

        # Call GO-OUT agent
        goout_result = self._goout_agent_node(updated_state)

        # Mark that we should store these events
        return {
            "messages": ra_result["messages"] + goout_result["messages"],
            "should_store": True
        }

    def _storage_node(self, state: AgentState) -> Dict[str, Any]:
        """Store fetched events in vector store"""
        if not state.get("should_store", False):
            logger.info("Skipping storage - no new events to store")
            return {"messages": []}

        # Get events from messages (skip first message which is user query)
        event_messages = [msg for msg in state["messages"][1:] if hasattr(msg, 'name') and msg.name in ["RAEvents", "GOOUTEvents"]]

        if not event_messages:
            logger.warning("No event messages to store")
            return {"messages": []}

        # Convert to format for storage
        events_data = [
            {"name": msg.name, "content": msg.content}
            for msg in event_messages
        ]

        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")
        location = state.get("location", "")

        logger.info(f"Storing {len(events_data)} event sources in vector store")

        # Store in vector store
        self.vector_store.store_events(
            events_data=events_data,
            start_date=start_date,
            end_date=end_date,
            location=location
        )

        return {"messages": []}

    def _ra_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """RA Events agent node - fetches events from Resident Advisor"""
        messages = state["messages"]

        # Get the user query
        user_message = messages[0].content if messages else ""

        # Create model with tool binding
        model_with_tools = self.model.bind_tools([fetch_ra_events])

        # Get current date for context
        today = datetime.now()
        current_date_str = today.strftime("%Y-%m-%d")
        day_of_week = today.strftime("%A")
        current_weekday = today.weekday()  # 0=Monday, 6=Sunday

        # Calculate common date ranges
        # This weekend: If Mon-Thu → Fri-Sun, If Fri → Fri-Sun, If Sat-Sun → Sat-Sun
        if current_weekday <= 4:  # Monday to Friday
            days_until_friday = (4 - current_weekday) % 7
            this_weekend_start = today + timedelta(days=days_until_friday)
            this_weekend_end = this_weekend_start + timedelta(days=2)  # Friday to Sunday
        else:  # Saturday or Sunday
            this_weekend_start = today
            days_until_sunday = 6 - current_weekday
            this_weekend_end = today + timedelta(days=days_until_sunday)

        # Next weekend: Always the following Friday-Sunday
        days_until_next_friday = (4 - current_weekday + 7) % 7
        if days_until_next_friday == 0 and current_weekday != 4:
            days_until_next_friday = 7
        next_weekend_start = today + timedelta(days=days_until_next_friday)
        next_weekend_end = next_weekend_start + timedelta(days=2)

        # Tomorrow and tonight
        tomorrow = today + timedelta(days=1)
        tonight = today

        # System prompt with current date context
        system_msg = f"""You are a Resident Advisor events specialist. Fetch electronic music events using fetch_ra_events.

        CURRENT DATE AND TIME CONTEXT:
        - Today is: {current_date_str} ({day_of_week})
        - Current time: {today.strftime("%H:%M")}

        RELATIVE DATE CALCULATIONS (use these exact dates):
        - "tonight" or "today" → {tonight.strftime("%Y-%m-%d")}
        - "tomorrow" → {tomorrow.strftime("%Y-%m-%d")}
        - "this weekend" → {this_weekend_start.strftime("%Y-%m-%d")} to {this_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
        - "next weekend" → {next_weekend_start.strftime("%Y-%m-%d")} to {next_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
        - "this week" → {today.strftime("%Y-%m-%d")} to {(today + timedelta(days=6-current_weekday)).strftime("%Y-%m-%d")} (today through Sunday)
        - "next week" → {(today + timedelta(days=7-current_weekday)).strftime("%Y-%m-%d")} to {(today + timedelta(days=13-current_weekday)).strftime("%Y-%m-%d")} (next Monday through Sunday)

        IMPORTANT: When user says "this weekend", use the EXACT dates shown above for this weekend.

        Supported locations: greece, athens, berlin, london, newyork, amsterdam

        Always use custom date ranges when calling the tool:
        - Use start_date and end_date parameters in YYYY-MM-DD format
        - Examples:
          * "events this weekend in Athens" → start_date="{this_weekend_start.strftime("%Y-%m-%d")}", end_date="{this_weekend_end.strftime("%Y-%m-%d")}", location="athens"
          * "events Nov 1-5" → start_date="2025-11-01", end_date="2025-11-05"
          * "events tomorrow" → start_date="{tomorrow.strftime("%Y-%m-%d")}", end_date="{tomorrow.strftime("%Y-%m-%d")}"

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

        # Get current date for context
        today = datetime.now()
        current_date_str = today.strftime("%Y-%m-%d")
        day_of_week = today.strftime("%A")
        current_weekday = today.weekday()  # 0=Monday, 6=Sunday

        # Calculate common date ranges
        # This weekend: If Mon-Thu → Fri-Sun, If Fri → Fri-Sun, If Sat-Sun → Sat-Sun
        if current_weekday <= 4:  # Monday to Friday
            days_until_friday = (4 - current_weekday) % 7
            this_weekend_start = today + timedelta(days=days_until_friday)
            this_weekend_end = this_weekend_start + timedelta(days=2)  # Friday to Sunday
        else:  # Saturday or Sunday
            this_weekend_start = today
            days_until_sunday = 6 - current_weekday
            this_weekend_end = today + timedelta(days=days_until_sunday)

        # Next weekend: Always the following Friday-Sunday
        days_until_next_friday = (4 - current_weekday + 7) % 7
        if days_until_next_friday == 0 and current_weekday != 4:
            days_until_next_friday = 7
        next_weekend_start = today + timedelta(days=days_until_next_friday)
        next_weekend_end = next_weekend_start + timedelta(days=2)

        # Tomorrow and tonight
        tomorrow = today + timedelta(days=1)
        tonight = today

        # System prompt with current date context
        system_msg = f"""You are a GO-OUT events specialist. Fetch nightlife, concerts, and sports events using fetch_goout_events.

        CURRENT DATE AND TIME CONTEXT:
        - Today is: {current_date_str} ({day_of_week})
        - Current time: {today.strftime("%H:%M")}

        RELATIVE DATE CALCULATIONS (use these exact dates):
        - "tonight" or "today" → {tonight.strftime("%Y-%m-%d")}
        - "tomorrow" → {tomorrow.strftime("%Y-%m-%d")}
        - "this weekend" → {this_weekend_start.strftime("%Y-%m-%d")} to {this_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
        - "next weekend" → {next_weekend_start.strftime("%Y-%m-%d")} to {next_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
        - "this week" → {today.strftime("%Y-%m-%d")} to {(today + timedelta(days=6-current_weekday)).strftime("%Y-%m-%d")} (today through Sunday)
        - "next week" → {(today + timedelta(days=7-current_weekday)).strftime("%Y-%m-%d")} to {(today + timedelta(days=13-current_weekday)).strftime("%Y-%m-%d")} (next Monday through Sunday)

        IMPORTANT: When user says "this weekend", use the EXACT dates shown above for this weekend.

        Categories: nightlife, concerts, sports, all
        Location filtering: athens, amsterdam, paris, toronto, etc. (searches in address)

        Always use custom date ranges when calling the tool:
        - Use start_date and end_date parameters in YYYY-MM-DD format
        - Examples:
          * "nightlife tonight" → category="nightlife", start_date="{tonight.strftime("%Y-%m-%d")}", end_date="{tonight.strftime("%Y-%m-%d")}"
          * "concerts this weekend in Athens" → category="concerts", location="athens", start_date="{this_weekend_start.strftime("%Y-%m-%d")}", end_date="{this_weekend_end.strftime("%Y-%m-%d")}"
          * "nightlife Nov 1-5" → category="nightlife", start_date="2025-11-01", end_date="2025-11-05"

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

            # Execute query through graph with state
            result = await self.graph.ainvoke({
                "messages": [HumanMessage(content=enhanced_query)],
                "start_date": start_date,
                "end_date": end_date,
                "location": location,
                "should_store": False,
                "next": ""
            })

            return result

        except Exception as e:
            logger.error(f"Error in fetch_events: {str(e)}")
            raise
