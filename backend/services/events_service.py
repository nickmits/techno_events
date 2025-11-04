"""
Events Service - Integrates LangGraph multi-agent system for event discovery
"""

from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
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
from backend.tools.tavily_search import get_tavily_search_tool
from backend.services.vector_store_service import VectorStoreService
from backend.services.geocoding_service import GeocodingService

load_dotenv()

logger = logging.getLogger(__name__)


class SupervisorDecision(BaseModel):
    """Schema for LLM-based supervisor routing decision"""
    action: Literal["retrieve_csv", "fetch_web"] = Field(
        description="The action to take: 'retrieve_csv' from cache or 'fetch_web' from APIs"
    )
    reasoning: str = Field(
        description="Brief explanation for the routing decision"
    )


class QueryValidation(BaseModel):
    """Schema for validating if query is about events"""
    is_events_related: bool = Field(
        description="True if query is about events, music, venues, nightlife. False if completely off-topic."
    )
    reasoning: str = Field(
        description="Brief explanation for the validation decision"
    )


# Removed old create_supervisor function - now using LLM-based supervisor directly in node


class AgentState(TypedDict):
    """State shared between agents"""
    messages: Annotated[List[BaseMessage], operator.add]
    next: str
    start_date: Optional[str]
    end_date: Optional[str]
    location: Optional[str]
    user_lat: Optional[float]  # User's latitude for distance calculation
    user_lon: Optional[float]  # User's longitude for distance calculation
    retrieved_events: Optional[List[Dict[str, Any]]]  # Events from CSV or web
    events_count: int  # Number of events retrieved
    source: str  # "csv", "web", or "web_search"
    final_response: Optional[str]  # Generated conversational response
    is_valid_query: bool  # Whether query is about events
    interrupt: Optional[dict]  # Interrupt payload for human-in-the-loop


class EventsService:
    """Service for managing event queries through LangGraph"""

    def __init__(self):
        """Initialize the service and build the LangGraph"""
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.model = ChatOpenAI(model="gpt-4o-mini")
        self.graph = None
        self.checkpointer = MemorySaver()  # For interrupt/resume
        self.vector_store = VectorStoreService()
        self.geocoding_service = GeocodingService()  # Initialize geocoding service
        self.tools = self._get_tool_belt()  # Initialize tool belt
        logger.info("EventsService initialized with vector store, geocoding service, and tools")

    def _get_tool_belt(self) -> List:
        """Return the list of tools available for event fetching (RA.co and GO-OUT)."""
        return [fetch_ra_events, fetch_goout_events]

    async def _build_graph(self):
        """Build the multi-agent graph with human-in-the-loop for location"""

        graph = StateGraph(AgentState)

        # Create ToolNode for automatic tool execution
        tool_node = ToolNode(self.tools)

        # Add nodes
        graph.add_node("ParseDates", self._parse_dates_node)
        graph.add_node("CheckCompleteness", self._check_completeness_node)
        graph.add_node("AskForLocation", self._ask_for_location_node)
        graph.add_node("CSVRetrieval", self._csv_retrieval_node)
        graph.add_node("WebAgent", self._web_agent_node)  # LLM with tools bound
        graph.add_node("CallTools", tool_node)  # ToolNode executes automatically
        graph.add_node("StoreEvents", self._storage_node)  # Store RA/GO-OUT events in CSV
        graph.add_node("WebSearchAgent", self._web_search_agent_node)  # Tavily fallback
        graph.add_node("SortByDistance", self._sort_by_distance_node)  # Sort events by proximity
        graph.add_node("GenerateResponse", self._generate_conversational_response_node)

        # Set entry point
        graph.set_entry_point("ParseDates")

        # Route from ParseDates to CheckCompleteness
        graph.add_edge("ParseDates", "CheckCompleteness")

        # Routing function - check if we need to ask for location, or route to data source
        def route_completeness_check(state: AgentState) -> str:
            """Check if we have dates but no location → ask for location, otherwise route to CSV/Web"""
            start_date = state.get("start_date")
            end_date = state.get("end_date")
            user_lat = state.get("user_lat")
            user_lon = state.get("user_lon")

            # If we have dates but no user location, ask for it
            if (start_date or end_date) and (user_lat is None or user_lon is None):
                logger.info("📍 Have dates but no location → AskForLocation")
                return "ask_location"

            # Otherwise, do data source routing directly
            location = "athens"

            # CASE 1: If dates are provided, check if CSV has data for those exact dates
            if start_date and end_date:
                events_exist = self.vector_store.check_events_exist(start_date, end_date, location)
                if events_exist:
                    logger.info("📊 Routing: CSV has data for specified dates → CSVRetrieval")
                    return "csv"
                else:
                    logger.info("🌐 Routing: No CSV data for specified dates → WebAgent")
                    return "web"

            # CASE 2: No dates parsed - still try CSV if it has ANY events (semantic search by venue/query)
            if self.vector_store.events_df is not None and len(self.vector_store.events_df) > 0:
                logger.info("📊 Routing: No dates parsed, but CSV has events → CSVRetrieval (semantic search)")
                return "csv"

            logger.info("🌐 Routing: CSV empty → WebAgent")
            return "web"

        # Route from CheckCompleteness to AskForLocation, CSVRetrieval, or WebAgent
        graph.add_conditional_edges(
            "CheckCompleteness",
            route_completeness_check,
            {
                "ask_location": "AskForLocation",
                "csv": "CSVRetrieval",
                "web": "WebAgent"
            }
        )

        # Routing function for after AskForLocation
        def route_after_location(state: AgentState) -> str:
            """Route to data source after getting location"""
            start_date = state.get("start_date")
            end_date = state.get("end_date")
            location = "athens"

            # Same logic as route_data_source
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

        # Route from AskForLocation to CSVRetrieval or WebAgent
        graph.add_conditional_edges(
            "AskForLocation",
            route_after_location,
            {
                "csv": "CSVRetrieval",
                "web": "WebAgent"
            }
        )

        # CSV path: CSVRetrieval → check if has events → SortByDistance or WebAgent
        def route_csv_results(state: AgentState) -> str:
            """Check if CSV returned events"""
            events_count = state.get("events_count", 0)
            if events_count > 0:
                return "sort"
            return "web"  # Fallback to web if CSV empty

        graph.add_conditional_edges(
            "CSVRetrieval",
            route_csv_results,
            {"sort": "SortByDistance", "web": "WebAgent"}
        )

        # Web path: WebAgent → check if tool_calls → CallTools or GenerateResponse
        def route_web_agent(state: AgentState) -> str:
            """Check if WebAgent called tools"""
            last_message = state["messages"][-1]
            if getattr(last_message, "tool_calls", None):
                return "tools"
            return "response"

        graph.add_conditional_edges(
            "WebAgent",
            route_web_agent,
            {"tools": "CallTools", "response": "GenerateResponse"}
        )

        # After CallTools → check if events found → StoreEvents or WebSearchAgent (Tavily fallback)
        def route_tool_results(state: AgentState) -> str:
            """Check if RA/GO-OUT tools found events, fallback to Tavily if not"""
            # Parse tool messages to count events
            messages = state.get("messages", [])
            tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]

            if tool_messages:
                # Quick check: parse tool messages to see if events were found
                events = self._parse_tool_messages(tool_messages, "")
                events_count = len(events)

                if events_count > 0:
                    logger.info(f"✅ RA/GO-OUT found {events_count} events → StoreEvents → GenerateResponse")
                    return "store"
                else:
                    logger.info("⚠️ RA/GO-OUT found 0 events → WebSearchAgent (Tavily fallback)")
                    return "websearch"

            # No tool messages, go to response
            return "store"

        graph.add_conditional_edges(
            "CallTools",
            route_tool_results,
            {"store": "StoreEvents", "websearch": "WebSearchAgent"}
        )

        # After StoreEvents, go to SortByDistance
        graph.add_edge("StoreEvents", "SortByDistance")

        # After WebSearchAgent, go to SortByDistance
        graph.add_edge("WebSearchAgent", "SortByDistance")

        # After SortByDistance, go to GenerateResponse
        graph.add_edge("SortByDistance", "GenerateResponse")

        # After response, END
        graph.add_edge("GenerateResponse", END)

        return graph.compile(checkpointer=self.checkpointer)

    def _validate_query_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Validate if the user query is actually about events, music, venues, nightlife.
        If completely off-topic, mark as invalid and generate polite rejection.
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        logger.info(f"Validating query: {user_query}")

        # Create validation model
        validation_model = self.model.with_structured_output(QueryValidation)

        prompt = f"""Analyze this user query and determine if it's about events, music, nightlife, venues, concerts, or parties.

User Query: "{user_query}"

VALIDATION RULES:
- Return TRUE if query is about:
  * Events (techno, music, concerts, parties, festivals)
  * Venues, clubs, bars, nightlife
  * Artists, DJs, performances
  * Dates/times for events
  * General inquiries about "what's happening" in a location

- Return FALSE ONLY if query is COMPLETELY OFF-TOPIC:
  * Weather (unless asking about events in weather context)
  * Math homework, recipes, travel directions
  * Sports scores, news, politics
  * Product recommendations unrelated to nightlife
  * General knowledge questions

Be generous - if there's ANY connection to events or nightlife, return TRUE.

Is this query about events/nightlife?"""

        try:
            validation = validation_model.invoke([HumanMessage(content=prompt)])
            is_valid = validation.is_events_related
            reasoning = validation.reasoning

            logger.info(f"Query validation: is_valid={is_valid}, reasoning={reasoning}")

            if not is_valid:
                # Generate polite rejection message
                rejection_msg = f"""I'm an events assistant specialized in techno and electronic music events.
Your question seems to be about something else: "{user_query}"

I can help you find:
- Techno and electronic music events
- Club nights and parties
- Upcoming concerts and festivals
- Venue information
- Artist lineups

Would you like to know about any upcoming events?"""

                return {
                    "is_valid_query": False,
                    "final_response": rejection_msg,
                    "messages": []
                }

            return {
                "is_valid_query": True,
                "messages": []
            }

        except Exception as e:
            logger.error(f"Error validating query: {e}")
            # If validation fails, assume query is valid (fail open)
            return {
                "is_valid_query": True,
                "messages": []
            }

    def _parse_dates_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Parse natural language dates from the query.
        Extracts start_date and end_date.
        ATHENS-ONLY: Location is always 'athens', no need to parse it.
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        # Skip if dates already provided in state
        if state.get("start_date") and state.get("end_date"):
            logger.info(f"Dates already provided: {state['start_date']} to {state['end_date']}")
            return {"messages": []}

        try:
            # Get current date for context
            from datetime import datetime, timedelta
            today = datetime.now().date()

            # Calculate this weekend and next weekend for context
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0 and today.weekday() >= 4:  # If Friday or weekend
                this_weekend_start = today
            else:
                this_weekend_start = today + timedelta(days=days_until_friday)
            this_weekend_end = this_weekend_start + timedelta(days=2)

            days_until_next_friday = days_until_friday + 7 if days_until_friday > 0 else 7
            next_weekend_start = today + timedelta(days=days_until_next_friday)
            next_weekend_end = next_weekend_start + timedelta(days=2)

            prompt = f"""Today is {today.strftime("%Y-%m-%d")} ({today.strftime("%A")}).

Parse the following query and extract the date range and location:

Query: "{user_query}"

Reference dates:
- "this weekend" = {this_weekend_start.strftime("%Y-%m-%d")} to {this_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
- "next weekend" = {next_weekend_start.strftime("%Y-%m-%d")} to {next_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
- "tonight" = {today.strftime("%Y-%m-%d")}
- "tomorrow" = {(today + timedelta(days=1)).strftime("%Y-%m-%d")}
- "this week" = {today.strftime("%Y-%m-%d")} to {(today + timedelta(days=6)).strftime("%Y-%m-%d")}
- "next week" = {(today + timedelta(days=7)).strftime("%Y-%m-%d")} to {(today + timedelta(days=13)).strftime("%Y-%m-%d")}

Respond in JSON format ONLY:
{{
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null"
}}

If no specific dates mentioned, use null for start_date and end_date (don't assume dates).

Examples:
- "events this weekend" → {{"start_date": "{this_weekend_start.strftime("%Y-%m-%d")}", "end_date": "{this_weekend_end.strftime("%Y-%m-%d")}"}}
- "what's happening tonight" → {{"start_date": "{today.strftime("%Y-%m-%d")}", "end_date": "{today.strftime("%Y-%m-%d")}"}}
- "tell me about techno events" → {{"start_date": null, "end_date": null}}

Respond with JSON only:"""

            response = self.model.invoke([HumanMessage(content=prompt)])
            result_text = response.content.strip()

            # Parse JSON response
            import json
            import re
            # Extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)

            parsed = json.loads(result_text)

            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")

            # Update state with parsed dates (location is always athens)
            updates = {"messages": []}
            if start_date and start_date != "null":
                updates["start_date"] = start_date
            if end_date and end_date != "null":
                updates["end_date"] = end_date

            logger.info(f"Parsed dates from query: start={updates.get('start_date')}, end={updates.get('end_date')}")

            return updates

        except Exception as e:
            logger.error(f"Error parsing dates: {e}")
            # If parsing fails, continue without dates
            return {"messages": []}

    def _check_completeness_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Check if we have dates AND user location.
        If dates exist but no location, we need to ask for location.
        """
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        user_lat = state.get("user_lat")
        user_lon = state.get("user_lon")

        logger.info(f"Checking completeness: dates={start_date}/{end_date}, location={user_lat}/{user_lon}")

        # No changes needed, just pass through
        return {"messages": []}

    def _ask_for_location_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Ask user for location using interrupt() pattern.
        After user responds, geocode their location and update state.
        """
        start_date = state.get("start_date")
        end_date = state.get("end_date")

        logger.info(f"📍 Asking user for location (dates: {start_date} to {end_date})")

        # Prepare interrupt payload
        location_request = f"Great! I found events from {start_date} to {end_date}. Where are you located in Athens? (e.g., Syntagma Square, Monastiraki, Exarchia)"

        interrupt_payload = {
            "type": "location_request",
            "message": location_request,
            "dates": {"start": start_date, "end": end_date}
        }

        # Interrupt and ask for location (this will cause graph to return on first call)
        user_location_input = interrupt(interrupt_payload)

        logger.info(f"✅ User provided location: {user_location_input}")

        # Geocode the user's location
        user_coords = self.geocoding_service.geocode_venue(user_location_input)

        if user_coords:
            user_lat, user_lon = user_coords
            logger.info(f"📍 Geocoded user location: ({user_lat}, {user_lon})")
        else:
            logger.warning(f"⚠️ Could not geocode user location: {user_location_input}")
            # Use default (Syntagma Square)
            user_lat, user_lon = 37.9755, 23.7348
            logger.info(f"📍 Using default location (Syntagma): ({user_lat}, {user_lon})")

        # Update state with geocoded location (clear interrupt after resume)
        return {
            "user_lat": user_lat,
            "user_lon": user_lon,
            "interrupt": None,  # Clear interrupt after resume
            "messages": []
        }

    # OLD NODES REMOVED - Simplified to routing functions in _build_graph()
    # _supervisor_node → route_data_source() function
    # _route_supervisor → integrated into conditional_edges
    # _check_csv_results_node → route_csv_results() function
    # _parse_tool_results_node → _parse_tool_messages() helper + integrated into GenerateResponse

    def _csv_retrieval_node(self, state: AgentState) -> Dict[str, Any]:
        """
        CSV Retrieval Node - searches Athens events from vector store
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        # Get date filters from state
        start_date = state.get("start_date")
        end_date = state.get("end_date")

        # ATHENS-ONLY: Always use athens
        location = "athens"

        logger.info(f"Retrieving Athens events from vector store for query: {user_query}")

        # Query vector store with metadata filters
        events = self.vector_store.retrieve_events(
            query=user_query,
            k=20,
            start_date=start_date,
            end_date=end_date,
            location=location
        )

        # Store as structured data for later use
        state["retrieved_events"] = events
        state["events_count"] = len(events)
        state["source"] = "csv"

        logger.info(f"Retrieved {len(events)} Athens events from CSV")

        return {
            "retrieved_events": events,
            "events_count": len(events),
            "source": "csv",
            "messages": []
        }

    # _check_csv_results_node REMOVED - logic moved to route_csv_results() in _build_graph()

    def _generate_conversational_response_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Generate conversational response - handles CSV, Web (ToolNode), and WebSearch (Tavily) results
        PRIORITY: State retrieved_events (from CSV/Tavily) > ToolMessages (from RA/GO-OUT)
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        # IMPORTANT: Check state first (WebSearchAgent or CSV sets this)
        # If retrieved_events exist in state, use them (they override ToolMessages)
        if state.get("retrieved_events") is not None:
            # Use events from state (CSV or WebSearchAgent)
            events = state.get("retrieved_events", [])
            events_count = state.get("events_count", 0)
            source = state.get("source", "csv")
            logger.info(f"Using events from state: {events_count} events from {source}")
        else:
            # Fallback: Parse ToolMessages from CallTools (RA/GO-OUT)
            tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
            if tool_messages:
                logger.info(f"📦 Parsing {len(tool_messages)} tool result(s) from ToolNode")
                events = self._parse_tool_messages(tool_messages, user_query)
                events_count = len(events)
                source = "web"
            else:
                # No events at all
                events = []
                events_count = 0
                source = "unknown"

        logger.info(f"Generating conversational response for {events_count} events from {source}")

        # Handle no events - check if query is actually about events
        if events_count == 0:
            # Use LLM to generate helpful response (not just generic message)
            try:
                prompt = f"""The user asked: "{user_query}"

We searched for events but found nothing. Analyze the query and respond appropriately:

1. If they asked "what is [something]?" (e.g., "what is techno?", "what is Burger Disco Club?"):
   - Provide a helpful explanation if you know
   - If it's a venue/club: explain it might be a local venue and suggest they try specific date queries
   - If it's a general question: answer briefly and offer to search for related events

2. If they searched for specific events but we found none:
   - Apologize politely
   - Suggest trying different dates or broader search terms
   - Offer alternative suggestions

Be helpful and conversational. Don't just say "no results found"."""

                response_msg = self.model.invoke([HumanMessage(content=prompt)])
                response = response_msg.content
            except Exception as e:
                logger.error(f"Error generating smart response: {e}")
                response = f"I couldn't find any events for '{user_query}'. Could you try a different date range or be more specific about what you're looking for?"

            return {
                "final_response": response,
                "retrieved_events": [],
                "events_count": 0,
                "source": source,
                "messages": [AIMessage(content=response)]
            }

        # Create a rich context about the events for the LLM
        events_context = []
        for i, event in enumerate(events[:15], 1):  # Top 15 events
            # For web search results, include description
            if source == "web_search" and event.get('description'):
                event_info = f"""
Result {i}: {event.get('title', 'Unknown Title')}
{event.get('description', '')}
{f"- URL: {event.get('url', '')}" if event.get('url') else ""}
"""
            else:
                # For RA/GO-OUT events, show structured data
                event_info = f"""
Event {i}: {event.get('title', 'Unknown Title')}
- Venue: {event.get('venue', 'TBA')}
- Date: {event.get('event_date', 'TBA')}
- Location: {event.get('location', 'Unknown')}
{f"- Attending: {event.get('attending', 'N/A')}" if event.get('attending') else ""}
{f"- Music: {event.get('music_types', '')}" if event.get('music_types') else ""}
{f"- URL: {event.get('url', '')}" if event.get('url') else ""}
"""
            events_context.append(event_info.strip())

        events_text = "\n\n".join(events_context)

        # Adapt prompt based on source
        if source == "web_search":
            prompt = f"""You are a helpful assistant for Athens nightlife and events.

User Query: "{user_query}"
Source: Web Search Results (Tavily)

{events_text}

The user's query might be asking about a venue, event, or general information.
Provide a helpful, informative response based on the web search results above:
- If they asked "what is [something]?", explain what it is based on the search results
- If it's about a venue/club, describe it and suggest when they might want to visit
- Be conversational and helpful
- Include relevant links if available"""
        else:
            prompt = f"""You are a helpful techno/electronic music events assistant for Athens.

User Query: "{user_query}"
Events Found: {events_count} events (showing top {min(15, events_count)})

{events_text}

Write a friendly, conversational response (2-3 paragraphs):
- Acknowledge their query
- Highlight 3-5 interesting events naturally
- Mention venues, dates, and any standout details
- Keep it conversational, like talking to a friend"""

        # Generate response using LLM
        try:
            response_msg = self.model.invoke([HumanMessage(content=prompt)])
            conversational_response = response_msg.content

            logger.info("Generated conversational response successfully")

            return {
                "final_response": conversational_response,
                "retrieved_events": events,  # Pass through the events
                "events_count": events_count,  # Pass through the count
                "source": source,  # Pass through the source
                "messages": [AIMessage(content=conversational_response)]
            }

        except Exception as e:
            logger.error(f"Error generating conversational response: {e}")
            # Fallback to simple response
            fallback = f"I found {events_count} events for your query. Here are some highlights: {events_text[:500]}..."
            return {
                "final_response": fallback,
                "retrieved_events": events,  # Pass through the events
                "events_count": events_count,  # Pass through the count
                "source": source,  # Pass through the source
                "messages": [AIMessage(content=fallback)]
            }

    def _web_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Web Agent - LLM with tools bound (RA.co and GO-OUT).
        Returns AIMessage with tool_calls. ToolNode executes them automatically.
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""
        start_date = state.get("start_date")
        end_date = state.get("end_date")

        # Get current date for context
        today = datetime.now()
        current_date_str = today.strftime("%Y-%m-%d")
        day_of_week = today.strftime("%A")

        # Bind tools to model (ToolNode pattern)
        model_with_tools = self.model.bind_tools(self.tools)

        # System prompt for the unified agent
        system_msg = f"""You are an events discovery agent for Athens with access to two event platforms.

CURRENT DATE: {current_date_str} ({day_of_week})

TOOLS AVAILABLE:
1. fetch_ra_events - Resident Advisor (electronic/techno music events)
2. fetch_goout_events - GO-OUT (nightlife, concerts, sports events)

USER QUERY: "{user_query}"
DATE RANGE: {start_date or 'not specified'} to {end_date or 'not specified'}
LOCATION: Athens

YOUR TASK:
- Call BOTH tools to get comprehensive event coverage from both platforms
- Use these exact parameters for BOTH tools:
  * start_date: "{start_date}"
  * end_date: "{end_date}"
  * location: "athens" (for fetch_ra_events)
  * location: "athens" (for fetch_goout_events)
  * category: "nightlife" (for fetch_goout_events)

IMPORTANT: You MUST call both tools to provide complete results!"""

        logger.info(f"🛠️ LLM deciding which tools to call...")

        # Invoke model - it returns AIMessage with tool_calls
        try:
            response = model_with_tools.invoke([
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_query}
            ])

            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"✅ LLM decided to call {len(response.tool_calls)} tool(s): {[tc['name'] for tc in response.tool_calls]}")
            else:
                logger.warning("⚠️ LLM did not call any tools!")

            # Return AIMessage - ToolNode will execute the tools in next step
            return {
                "messages": [response]
            }

        except Exception as e:
            logger.error(f"Error in web fetch node: {e}")
            # Return error message
            return {
                "messages": [AIMessage(content=f"Error preparing tool calls: {str(e)}")]
            }

    # _parse_tool_results_node REMOVED - logic moved to _parse_tool_messages() and _generate_conversational_response_node()

    def _parse_tool_messages(self, tool_messages: List[ToolMessage], user_query: str) -> List[Dict[str, Any]]:
        """
        Parse ToolMessages from ToolNode into structured event data
        """
        all_results = []
        for tool_msg in tool_messages:
            # Extract tool name
            tool_name = tool_msg.name if hasattr(tool_msg, 'name') else "UnknownTool"

            # Determine source name
            if "fetch_ra_events" in str(tool_name):
                source_name = "RAEvents"
            elif "fetch_goout_events" in str(tool_name):
                source_name = "GOOUTEvents"
            else:
                source_name = "WebEvents"

            # Parse the content
            events = self._parse_web_results_to_structured(tool_msg.content, source_name)
            all_results.extend(events)
            logger.info(f"  - {source_name}: {len(events)} events parsed")

        return all_results

    def _parse_web_results_to_structured(self, content: str, source: str) -> List[Dict[str, Any]]:
        """
        Parse web fetch results into structured event data for conversational response
        """
        events = []
        lines = content.split('\n')
        current_event = {}

        for line in lines:
            line = line.strip()

            # Check if this is the start of a new event (numbered line)
            if line and line[0].isdigit() and '. ' in line[:5]:
                # Save previous event if exists
                if current_event:
                    events.append(current_event)

                # Start new event
                title = line.split('. ', 1)[1] if '. ' in line else line
                current_event = {
                    "title": title,
                    "source": source,
                    "content": line
                }

            elif line and current_event:
                # Extract metadata
                if '📍' in line:
                    current_event["venue"] = line.replace('📍', '').strip()
                elif '📅' in line:
                    # Extract date
                    date_part = line.replace('📅', '').strip()
                    if date_part:
                        current_event["event_date"] = date_part.split(' ')[0]
                elif '👥' in line:
                    current_event["attending"] = line.replace('👥', '').replace('attending', '').strip()
                elif '🎵' in line:
                    current_event["music_types"] = line.replace('🎵', '').strip()
                elif '🔗' in line:
                    current_event["url"] = line.replace('🔗', '').strip()
                elif 'Location:' in line or 'location:' in line.lower():
                    current_event["location"] = line.split(':', 1)[1].strip() if ':' in line else ""

        # Add last event
        if current_event:
            events.append(current_event)

        return events

    def _web_search_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Web Search Agent - Fallback search using Tavily when RA/GO-OUT return 0 events
        Follows book_agent.py pattern - manual tool execution (not ToolNode)
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""
        start_date = state.get("start_date")
        end_date = state.get("end_date")

        logger.info(f"🌐 Web Search (Tavily): Searching for '{user_query}' as fallback...")

        try:
            # Get Tavily tool (manual execution like book_agent.py)
            tavily_tool = get_tavily_search_tool(max_results=5)

            # Construct search query
            search_query = f"{user_query} events Athens"
            if start_date:
                search_query += f" {start_date}"

            # Execute Tavily search
            results = tavily_tool.invoke({"query": search_query})

            # Format results
            web_info = f"🔍 Web Search Results for '{user_query}':\n\n{results}"

            logger.info(f"✅ Web search completed - found information")

            # Parse and structure web results (simplified)
            events = self._parse_tavily_results(results, user_query)

            return {
                "retrieved_events": events,
                "events_count": len(events),
                "source": "web_search",
                "messages": [AIMessage(content=f"🌐 Tavily Search: Found {len(events)} results from web")]
            }

        except Exception as e:
            logger.error(f"Error in web search: {e}")
            # Return empty results
            return {
                "retrieved_events": [],
                "events_count": 0,
                "source": "web_search",
                "messages": [AIMessage(content=f"⚠️ Web search unavailable: {str(e)}")]
            }

    def _parse_tavily_results(self, results: str, query: str) -> List[Dict[str, Any]]:
        """
        Parse Tavily search results into event-like format
        """
        # Tavily returns structured data - extract what we can
        events = []

        try:
            # If results is a string, create a single "event" with the info
            if isinstance(results, str):
                events.append({
                    "title": f"Web search results for: {query}",
                    "venue": "Various venues",
                    "event_date": "See details",
                    "description": results[:500],  # First 500 chars
                    "source": "Tavily Web Search",
                    "url": ""
                })
            elif isinstance(results, list):
                # If results is a list of dictionaries
                for idx, result in enumerate(results[:5], 1):
                    if isinstance(result, dict):
                        events.append({
                            "title": result.get("title", f"Web Result {idx}"),
                            "venue": "See link for details",
                            "event_date": "Various dates",
                            "description": result.get("content", result.get("snippet", ""))[:300],
                            "source": "Tavily Web Search",
                            "url": result.get("url", "")
                        })

        except Exception as e:
            logger.error(f"Error parsing Tavily results: {e}")

        return events

    def _storage_node(self, state: AgentState) -> Dict[str, Any]:
        """Store fetched events from RA/GO-OUT in vector store CSV"""
        messages = state.get("messages", [])
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")
        location = state.get("location", "athens")

        # Get ToolMessages from CallTools (RA/GO-OUT results)
        tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]

        if not tool_messages:
            logger.info("No tool messages to store")
            return {"messages": []}

        # Check if we have dates (required for storage)
        if not start_date or not end_date:
            logger.warning("No dates provided - skipping storage")
            return {"messages": []}

        # Convert ToolMessages to storage format
        events_data = []
        for tool_msg in tool_messages:
            tool_name = tool_msg.name if hasattr(tool_msg, 'name') else "UnknownTool"

            # Determine source name
            if "fetch_ra_events" in str(tool_name):
                source_name = "RAEvents"
            elif "fetch_goout_events" in str(tool_name):
                source_name = "GOOUTEvents"
            else:
                continue  # Skip unknown tools

            events_data.append({
                "name": source_name,
                "content": tool_msg.content
            })

        if not events_data:
            logger.info("No RA/GO-OUT events to store")
            return {"messages": []}

        logger.info(f"💾 Storing {len(events_data)} event source(s) in CSV for {start_date} to {end_date}")

        try:
            # Store in vector store (will parse and save to CSV)
            self.vector_store.store_events(
                events_data=events_data,
                start_date=start_date,
                end_date=end_date,
                location=location
            )
            logger.info(f"✅ Successfully stored events in CSV")
        except Exception as e:
            logger.error(f"❌ Error storing events: {e}")

        # Parse tool messages to extract structured events for downstream processing
        parsed_events = self._parse_tool_messages(tool_messages, "")
        logger.info(f"✅ Populated {len(parsed_events)} events for distance calculation")

        # Return populated state so SortByDistance can process the events
        return {
            "retrieved_events": parsed_events,
            "events_count": len(parsed_events),
            "source": "web",
            "messages": []
        }

    def _sort_by_distance_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Geocode venues and calculate distances from user location (if provided).
        Always geocodes venues to get lat/lon, calculates distances only if user location available.
        """
        user_lat = state.get("user_lat")
        user_lon = state.get("user_lon")
        retrieved_events = state.get("retrieved_events", [])

        # If no events, skip
        if not retrieved_events:
            logger.info("⏭️ No events to process")
            return {"messages": []}

        try:
            # CASE 1: User location is available → geocode venues AND calculate distances
            if user_lat and user_lon:
                logger.info(f"📍 Geocoding {len(retrieved_events)} venues and calculating distances from user location ({user_lat}, {user_lon})")

                # Sort events by distance (also geocodes venues and adds distance data)
                user_coords = (user_lat, user_lon)
                sorted_events = self.geocoding_service.sort_events_by_distance(retrieved_events, user_coords)

                closest_distance = next((e.get('distance_km') for e in sorted_events if e.get('distance_km') is not None), 'N/A')
                logger.info(f"✅ Events sorted by distance (closest: {closest_distance} km)")

                return {
                    "retrieved_events": sorted_events,
                    "messages": []
                }

            # CASE 2: No user location → geocode venues only (no distance calculation)
            else:
                logger.info(f"📍 Geocoding {len(retrieved_events)} venues (no user location for distance calculation)")

                # Geocode each venue to get lat/lon (but skip distance calculation)
                geocoded_events = []
                for event in retrieved_events:
                    venue_address = event.get("venue", "")

                    if venue_address and venue_address != "TBA":
                        # Geocode the venue
                        venue_coords = self.geocoding_service.geocode_venue(venue_address)

                        if venue_coords:
                            event["venue_lat"] = venue_coords[0]
                            event["venue_lon"] = venue_coords[1]
                        else:
                            event["venue_lat"] = None
                            event["venue_lon"] = None
                    else:
                        event["venue_lat"] = None
                        event["venue_lon"] = None

                    # Keep distance fields as None (no user location)
                    event["distance_km"] = None
                    event["drive_time_min"] = None
                    event["walk_time_min"] = None

                    geocoded_events.append(event)

                logger.info(f"✅ Geocoded {len([e for e in geocoded_events if e.get('venue_lat')])} venues")

                return {
                    "retrieved_events": geocoded_events,
                    "messages": []
                }

        except Exception as e:
            logger.error(f"❌ Error in distance/geocoding node: {e}")
            # Return original events if processing fails
            return {"messages": []}


    async def fetch_events(
        self,
        query: str,
        location: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ahead: Optional[int] = 30,
        thread_id: Optional[str] = None,
        resume_value: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch events using the LangGraph multi-agent system with human-in-the-loop
        ATHENS-ONLY: Location is always 'athens', parameter kept for API compatibility

        Args:
            query: Natural language query
            location: Ignored - always uses Athens
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            days_ahead: Days ahead if dates not specified
            thread_id: Thread ID for checkpoint/resume (human-in-the-loop)
            resume_value: User's response when resuming from interrupt (e.g., location)

        Returns:
            Dictionary containing messages from all agents, or interrupt payload
        """
        try:
            # Build graph if not already built
            if self.graph is None:
                logger.info("Building LangGraph...")
                self.graph = await self._build_graph()

            # ATHENS-ONLY: Always use athens, ignore location parameter
            location = "athens"

            # Configure checkpoint with thread_id
            config = {"configurable": {"thread_id": thread_id}} if thread_id else {}

            # If resuming from interrupt, provide the resume value
            if resume_value and thread_id:
                logger.info(f"🔄 Resuming thread {thread_id} with value: {resume_value}")

                # Resume the graph by invoking with None (checkpointer handles resume)
                # The resume_value is passed as input to the interrupted node
                result = await self.graph.ainvoke(
                    Command(resume=resume_value),
                    config=config
                )

                return result

            # Don't add "in Athens" to query since it's implicit
            enhanced_query = query
            if start_date and end_date:
                enhanced_query += f" between {start_date} and {end_date}"
            elif start_date:
                enhanced_query += f" starting from {start_date}"

            logger.info(f"Executing Athens query: {enhanced_query}")

            # Execute query through graph with state and config
            result = await self.graph.ainvoke(
                {
                    "messages": [HumanMessage(content=enhanced_query)],
                    "start_date": start_date,
                    "end_date": end_date,
                    "location": location,  # Always "athens"
                    "user_lat": None,  # Will be set by AskForLocation node
                    "user_lon": None,  # Will be set by AskForLocation node
                    "next": "",
                    "retrieved_events": None,
                    "events_count": 0,
                    "source": "",
                    "final_response": None,
                    "is_valid_query": True,
                    "interrupt": None
                },
                config=config
            )

            # Check if graph was interrupted (final_response will be None if interrupted)
            # This happens when the graph stops before reaching GenerateResponse node
            if result.get("final_response") is None:
                # Graph was interrupted - construct interrupt payload
                logger.info(f"🛑 Graph interrupted, waiting for user input")

                # Create interrupt payload (for location request)
                interrupt_payload = {
                    "type": "location_request",
                    "message": f"Great! I found events from {result.get('start_date')} to {result.get('end_date')}. Where are you located in Athens? (e.g., Syntagma Square, Monastiraki, Exarchia)",
                    "dates": {
                        "start": result.get("start_date"),
                        "end": result.get("end_date")
                    }
                }

                # Return result with interrupt payload
                result["interrupt"] = interrupt_payload
                return result

            return result

        except Exception as e:
            logger.error(f"Error in fetch_events: {str(e)}")
            raise
