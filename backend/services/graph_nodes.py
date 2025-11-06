"""
LangGraph node implementations for the events service
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import interrupt
import logging
import json
import re

from backend.services.graph_schemas import AgentState
from backend.services.tool_parsers import parse_tool_messages, parse_tavily_results
from backend.tools.tavily_search import get_tavily_search_tool

logger = logging.getLogger(__name__)


class GraphNodes:
    """Collection of LangGraph node implementations"""

    def __init__(self, model, vector_store, geocoding_service, tools):
        self.model = model
        self.vector_store = vector_store
        self.geocoding_service = geocoding_service
        self.tools = tools

    def parse_dates_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Parse natural language dates from the query.
        Extracts start_date and end_date.
        """
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        # Skip if dates already provided in state
        if state.get("start_date") and state.get("end_date"):
            logger.info(f"Dates already provided: {state['start_date']} to {state['end_date']}")
            return {"messages": []}

        try:
            today = datetime.now().date()

            # Calculate weekend dates for context
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0 and today.weekday() >= 4:
                this_weekend_start = today
            else:
                this_weekend_start = today + timedelta(days=days_until_friday)
            this_weekend_end = this_weekend_start + timedelta(days=2)

            days_until_next_friday = days_until_friday + 7 if days_until_friday > 0 else 7
            next_weekend_start = today + timedelta(days=days_until_next_friday)
            next_weekend_end = next_weekend_start + timedelta(days=2)

            prompt = f"""Today is {today.strftime("%Y-%m-%d")} ({today.strftime("%A")}).

Parse the following query and extract the date range:

Query: "{user_query}"

Reference dates:
- "this weekend" = {this_weekend_start.strftime("%Y-%m-%d")} to {this_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
- "next weekend" = {next_weekend_start.strftime("%Y-%m-%d")} to {next_weekend_end.strftime("%Y-%m-%d")} (Friday-Sunday)
- "tonight" = {today.strftime("%Y-%m-%d")}
- "tomorrow" = {(today + timedelta(days=1)).strftime("%Y-%m-%d")}

Respond in JSON format ONLY:
{{
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null"
}}

If no specific dates mentioned, use null (don't assume dates)."""

            response = self.model.invoke([HumanMessage(content=prompt)])
            result_text = response.content.strip()

            # Extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)

            parsed = json.loads(result_text)
            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")

            updates = {"messages": []}
            if start_date and start_date != "null":
                updates["start_date"] = start_date
            if end_date and end_date != "null":
                updates["end_date"] = end_date

            logger.info(f"Parsed dates: start={updates.get('start_date')}, end={updates.get('end_date')}")

            # Try to extract location from query if not already in state
            if not state.get("user_lat") or not state.get("user_lon"):
                location_keywords = [
                    "syntagma", "monastiraki", "psiri", "psirri", "gazi",
                    "exarchia", "exarcheia", "kolonaki", "metaxourgeio",
                    "thissio", "koukaki", "pagrati", "ampelokipoi"
                ]

                query_lower = user_query.lower()
                for keyword in location_keywords:
                    if keyword in query_lower:
                        logger.info(f"📍 Detected location keyword '{keyword}' in query")
                        coords = self.geocoding_service.geocode_venue(keyword + ", Athens, Greece")
                        if coords:
                            updates["user_lat"], updates["user_lon"] = coords
                            logger.info(f"✅ Geocoded '{keyword}' → ({coords[0]}, {coords[1]})")
                            break

            return updates

        except Exception as e:
            logger.error(f"Error parsing dates: {e}")
            return {"messages": []}

    def check_completeness_node(self, state: AgentState) -> Dict[str, Any]:
        """Check if we have dates AND user location."""
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        user_lat = state.get("user_lat")
        user_lon = state.get("user_lon")

        logger.info(f"Checking completeness: dates={start_date}/{end_date}, location={user_lat}/{user_lon}")
        return {"messages": []}

    def ask_for_location_node(self, state: AgentState) -> Dict[str, Any]:
        """Ask user for location using interrupt() pattern."""
        start_date = state.get("start_date")
        end_date = state.get("end_date")

        logger.info(f"📍 Asking user for location (dates: {start_date} to {end_date})")

        location_request = f"Great! I found events from {start_date} to {end_date}. Where are you located in Athens? (e.g., Syntagma Square, Monastiraki, Exarchia)"

        interrupt_payload = {
            "type": "location_request",
            "message": location_request,
            "dates": {"start": start_date, "end": end_date}
        }

        user_location_input = interrupt(interrupt_payload)
        logger.info(f"✅ User provided location: {user_location_input}")

        # Geocode the user's location
        user_coords = self.geocoding_service.geocode_venue(user_location_input)

        if user_coords:
            user_lat, user_lon = user_coords
            logger.info(f"📍 Geocoded user location: ({user_lat}, {user_lon})")
        else:
            logger.warning(f"⚠️ Could not geocode user location: {user_location_input}")
            user_lat, user_lon = 37.9755, 23.7348  # Default: Syntagma Square
            logger.info(f"📍 Using default location (Syntagma): ({user_lat}, {user_lon})")

        return {
            "user_lat": user_lat,
            "user_lon": user_lon,
            "interrupt": None,
            "messages": []
        }

    def csv_retrieval_node(self, state: AgentState) -> Dict[str, Any]:
        """CSV Retrieval Node - searches Athens events from vector store with filtering"""
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        start_date = state.get("start_date")
        end_date = state.get("end_date")
        location = "athens"

        logger.info(f"Retrieving events from vector store for query: {user_query}")

        events = self.vector_store.retrieve_events(
            query=user_query,
            k=30,  # Get more initially for filtering
            start_date=start_date,
            end_date=end_date,
            location=location
        )

        # Apply Athens-only filtering (in case CSV has non-Athens events)
        athens_events = self._filter_athens_only(events)

        # Apply deduplication
        unique_events = self._deduplicate_events(athens_events)

        # Limit to top 20 after filtering
        final_events = unique_events[:20]

        logger.info(f"Retrieved {len(final_events)} unique Athens events from CSV (after filtering)")

        return {
            "retrieved_events": final_events,
            "events_count": len(final_events),
            "source": "csv",
            "messages": []
        }

    def web_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """Web Agent - LLM with tools bound (RA.co and GO-OUT)"""
        messages = state["messages"]
        user_query = messages[0].content if messages else ""
        start_date = state.get("start_date")
        end_date = state.get("end_date")

        today = datetime.now()
        current_date_str = today.strftime("%Y-%m-%d")
        day_of_week = today.strftime("%A")

        model_with_tools = self.model.bind_tools(self.tools)

        system_msg = f"""You are an events discovery agent for Athens with access to two event platforms.

CURRENT DATE: {current_date_str} ({day_of_week})

TOOLS AVAILABLE:
1. fetch_ra_events - Resident Advisor (electronic/techno music events)
2. fetch_goout_events - GO-OUT (nightlife, concerts, sports events)

USER QUERY: "{user_query}"
DATE RANGE: {start_date or 'not specified'} to {end_date or 'not specified'}

YOUR TASK:
- Call BOTH tools to get comprehensive event coverage
- Use parameters: start_date="{start_date}", end_date="{end_date}", location="athens"

IMPORTANT: You MUST call both tools!"""

        logger.info(f"🛠️ LLM deciding which tools to call...")

        try:
            response = model_with_tools.invoke([
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_query}
            ])

            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"✅ LLM calling {len(response.tool_calls)} tool(s): {[tc['name'] for tc in response.tool_calls]}")
            else:
                logger.warning("⚠️ LLM did not call any tools!")

            return {"messages": [response]}

        except Exception as e:
            logger.error(f"Error in web fetch node: {e}")
            return {"messages": [AIMessage(content=f"Error preparing tool calls: {str(e)}")]}

    def _normalize_venue_name(self, venue: str) -> str:
        """Normalize venue name for comparison"""
        # Remove common prefixes/suffixes and clean up
        normalized = venue.lower().strip()
        # Remove address parts (after comma)
        if ',' in normalized:
            normalized = normalized.split(',')[0].strip()
        # Remove common words
        for word in ['club', 'athens', 'greece', 'bar']:
            normalized = normalized.replace(word, '').strip()
        return normalized

    def _deduplicate_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate events based on title, date, and venue"""
        seen = set()
        unique_events = []

        for event in events:
            # Create a key based on title, date, and normalized venue
            title = event.get("title", "").lower().strip()
            date = event.get("event_date", "")
            venue = self._normalize_venue_name(event.get("venue", ""))

            key = f"{title}|{date}|{venue}"

            if key not in seen:
                seen.add(key)
                unique_events.append(event)
            else:
                logger.info(f"🔄 Duplicate event removed: {event.get('title')} at {event.get('venue')}")

        logger.info(f"✅ Deduplication: {len(events)} events → {len(unique_events)} unique events ({len(events) - len(unique_events)} duplicates removed)")
        return unique_events

    def _filter_athens_only(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter events to only include those in Athens based on venue information"""
        athens_events = []

        # Athens keywords (both English and Greek)
        athens_keywords = [
            "athens", "athina", "αθήνα", "αθηνα",
            # Common Athens areas/neighborhoods
            "monastiraki", "μοναστηράκι",
            "psiri", "psirri", "ψυρρή", "ψυρρη",
            "gazi", "γκάζι",
            "exarchia", "exarcheia", "εξάρχεια",
            "syntagma", "σύνταγμα",
            "kolonaki", "κολωνάκι",
            "metaxourgeio", "μεταξουργείο",
            "thissio", "θησείο",
            "koukaki", "κουκάκι",
            "pagrati", "παγκράτι",
            "ampelokipoi", "αμπελόκηποι"
        ]

        # Explicit non-Athens keywords to catch edge cases
        explicit_non_athens = [
            "thessaloniki", "θεσσαλονίκη", "skg",
            "crete", "κρήτη",
            "pýrgos", "pyrgos", "πύργος",
            "ilia", "ηλεία"
        ]

        for event in events:
            venue = event.get("venue", "").lower()
            title = event.get("title", "").lower()

            # First check: explicitly exclude non-Athens cities
            is_explicitly_non_athens = any(
                keyword.lower() in venue or keyword.lower() in title
                for keyword in explicit_non_athens
            )

            if is_explicitly_non_athens:
                logger.info(f"📍 Filtered out non-Athens event: {event.get('title')} at {event.get('venue')}")
                continue

            # Second check: verify it contains Athens keywords
            has_athens_keyword = any(
                keyword.lower() in venue or keyword.lower() in title
                for keyword in athens_keywords
            )

            if has_athens_keyword:
                athens_events.append(event)
            else:
                # No Athens keyword found, log and skip
                logger.info(f"📍 Filtered out event (no Athens keyword): {event.get('title')} at {event.get('venue')}")

        logger.info(f"✅ Filtered {len(events)} events → {len(athens_events)} Athens events ({len(events) - len(athens_events)} removed)")
        return athens_events

    def storage_node(self, state: AgentState) -> Dict[str, Any]:
        """Store fetched events from RA/GO-OUT in vector store CSV, then retrieve via vector search"""
        messages = state.get("messages", [])
        user_query = messages[0].content if messages else ""
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")
        location = state.get("location", "athens")

        tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]

        if not tool_messages:
            logger.info("No tool messages to store")
            return {"messages": []}

        if not start_date or not end_date:
            logger.warning("No dates provided - skipping storage")
            return {"messages": []}

        events_data = []
        for tool_msg in tool_messages:
            tool_name = tool_msg.name if hasattr(tool_msg, 'name') else "UnknownTool"

            if "fetch_ra_events" in str(tool_name):
                source_name = "RAEvents"
            elif "fetch_goout_events" in str(tool_name):
                source_name = "GOOUTEvents"
            else:
                continue

            events_data.append({
                "name": source_name,
                "content": tool_msg.content
            })

        if not events_data:
            logger.info("No RA/GO-OUT events to store")
            return {"messages": []}

        logger.info(f"💾 Storing {len(events_data)} event source(s) in CSV for {start_date} to {end_date}")

        try:
            self.vector_store.store_events(
                events_data=events_data,
                start_date=start_date,
                end_date=end_date,
                location=location
            )
            logger.info(f"✅ Successfully stored events in CSV and rebuilt vector store")
        except Exception as e:
            logger.error(f"❌ Error storing events: {e}")

        # Now retrieve from vector store using semantic search (ensures consistency)
        logger.info(f"🔍 Retrieving stored events from vector store using semantic search")
        retrieved_events = self.vector_store.retrieve_events(
            query=user_query,
            k=20,
            start_date=start_date,
            end_date=end_date,
            location=location
        )

        logger.info(f"✅ Retrieved {len(retrieved_events)} events from vector store for response")

        return {
            "retrieved_events": retrieved_events,
            "events_count": len(retrieved_events),
            "source": "csv",  # Mark as csv since we retrieved from vector store
            "messages": []
        }

    def web_search_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """Web Search Agent - Fallback search using Tavily when RA/GO-OUT return 0 events"""
        messages = state["messages"]
        user_query = messages[0].content if messages else ""
        start_date = state.get("start_date")

        logger.info(f"🌐 Web Search (Tavily): Searching for '{user_query}' as fallback...")

        try:
            tavily_tool = get_tavily_search_tool(max_results=5)
            search_query = f"{user_query} events Athens"
            if start_date:
                search_query += f" {start_date}"

            results = tavily_tool.invoke({"query": search_query})
            logger.info(f"✅ Web search completed - found information")

            events = parse_tavily_results(results, user_query)

            return {
                "retrieved_events": events,
                "events_count": len(events),
                "source": "web_search",
                "messages": [AIMessage(content=f"🌐 Tavily Search: Found {len(events)} results from web")]
            }

        except Exception as e:
            logger.error(f"Error in web search: {e}")
            return {
                "retrieved_events": [],
                "events_count": 0,
                "source": "web_search",
                "messages": [AIMessage(content=f"⚠️ Web search unavailable: {str(e)}")]
            }

    def sort_by_distance_node(self, state: AgentState) -> Dict[str, Any]:
        """Geocode venues and calculate distances from user location (if provided)"""
        user_lat = state.get("user_lat")
        user_lon = state.get("user_lon")
        retrieved_events = state.get("retrieved_events", [])

        if not retrieved_events:
            logger.info("⏭️ No events to process")
            return {"messages": []}

        try:
            # CASE 1: User location available → geocode and calculate distances
            if user_lat and user_lon:
                logger.info(f"📍 Geocoding {len(retrieved_events)} venues and calculating distances")
                user_coords = (user_lat, user_lon)
                sorted_events = self.geocoding_service.sort_events_by_distance(retrieved_events, user_coords)

                closest_distance = next((e.get('distance_km') for e in sorted_events if e.get('distance_km') is not None), 'N/A')
                logger.info(f"✅ Events sorted by distance (closest: {closest_distance} km)")

                return {
                    "retrieved_events": sorted_events,
                    "messages": []
                }

            # CASE 2: No user location → geocode venues only
            else:
                logger.info(f"📍 Geocoding {len(retrieved_events)} venues (no user location)")
                geocoded_events = []
                for event in retrieved_events:
                    venue_address = event.get("venue", "")

                    if venue_address and venue_address != "TBA":
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
            return {"messages": []}

    def generate_conversational_response_node(self, state: AgentState) -> Dict[str, Any]:
        """Generate conversational response - handles CSV, Web, and WebSearch results"""
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        # Check state first (WebSearchAgent or CSV sets this)
        if state.get("retrieved_events") is not None:
            events = state.get("retrieved_events", [])
            events_count = state.get("events_count", 0)
            source = state.get("source", "csv")
            logger.info(f"Using events from state: {events_count} events from {source}")
        else:
            # Fallback: Parse ToolMessages from CallTools
            tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
            if tool_messages:
                logger.info(f"📦 Parsing {len(tool_messages)} tool result(s)")
                events = parse_tool_messages(tool_messages, user_query)
                events_count = len(events)
                source = "web"
            else:
                events = []
                events_count = 0
                source = "unknown"

        logger.info(f"Generating response for {events_count} events from {source}")

        # Handle no events
        if events_count == 0:
            try:
                prompt = f"""The user asked: "{user_query}"

We searched for events but found nothing. Respond appropriately:
- If they asked "what is [something]?", provide helpful explanation
- If they searched for specific events, suggest different dates or broader search terms

Be helpful and conversational."""

                response_msg = self.model.invoke([HumanMessage(content=prompt)])
                response = response_msg.content
            except Exception as e:
                logger.error(f"Error generating smart response: {e}")
                response = f"I couldn't find any events for '{user_query}'. Try a different date range or be more specific?"

            return {
                "final_response": response,
                "retrieved_events": [],
                "events_count": 0,
                "source": source,
                "messages": [AIMessage(content=response)]
            }

        # Create rich context for LLM
        events_context = []
        for i, event in enumerate(events[:15], 1):
            if source == "web_search" and event.get('description'):
                event_info = f"""Result {i}: {event.get('title', 'Unknown')}
{event.get('description', '')}
{f"- URL: {event.get('url', '')}" if event.get('url') else ""}"""
            else:
                event_info = f"""Event {i}: {event.get('title', 'Unknown')}
- Venue: {event.get('venue', 'TBA')}
- Date: {event.get('event_date', 'TBA')}
{f"- Attending: {event.get('attending', 'N/A')}" if event.get('attending') else ""}
{f"- URL: {event.get('url', '')}" if event.get('url') else ""}"""
            events_context.append(event_info.strip())

        events_text = "\n\n".join(events_context)

        # Adapt prompt based on source
        if source == "web_search":
            prompt = f"""You are a helpful assistant for Athens nightlife and events.

User Query: "{user_query}"
Source: Web Search Results (Tavily)

{events_text}

Provide a helpful, informative response based on the web search results.
Be conversational and include relevant links."""
        else:
            prompt = f"""You are a helpful techno/electronic music events assistant for Athens.

User Query: "{user_query}"
Events Found: {events_count} events (showing top {min(15, events_count)})

{events_text}

Write a friendly, conversational response (2-3 paragraphs):
- Highlight 3-5 interesting events naturally
- Mention venues, dates, and standout details
- Keep it conversational"""

        try:
            response_msg = self.model.invoke([HumanMessage(content=prompt)])
            conversational_response = response_msg.content
            logger.info("Generated conversational response successfully")

            return {
                "final_response": conversational_response,
                "retrieved_events": events,
                "events_count": events_count,
                "source": source,
                "messages": [AIMessage(content=conversational_response)]
            }

        except Exception as e:
            logger.error(f"Error generating conversational response: {e}")
            fallback = f"I found {events_count} events for your query. Here are some highlights: {events_text[:500]}..."
            return {
                "final_response": fallback,
                "retrieved_events": events,
                "events_count": events_count,
                "source": source,
                "messages": [AIMessage(content=fallback)]
            }
