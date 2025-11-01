"""
Multi-Agent LangGraph with Supervisor - RA Events Only (Simplified)
Tests the multi-agent setup without MCP async tools
"""

from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool
from typing import TypedDict, Annotated, List
from dotenv import load_dotenv
import functools
import operator
import asyncio
import os
import requests
import json
from datetime import datetime, timedelta

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    exit(1)

model = ChatOpenAI(model="gpt-4o-mini")


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next: str


# Common area IDs for RA.co GraphQL API
AREA_IDS = {
    "greece": 37,      # Greece (Athens area)
    "athens": 37,      # Athens, Greece
    "berlin": 34,      # Berlin, Germany
    "london": 13,      # London, UK
    "newyork": 6,      # New York, USA
    "amsterdam": 29,   # Amsterdam, Netherlands
}


@tool
def fetch_goout_events(category: str = "nightlife", location: str = None, start_date: str = None, end_date: str = None, days_ahead: int = 30) -> str:
    """
    Fetch nightlife, concerts, and sports events from GO-OUT.co API.

    Args:
        category: Event category (nightlife, concerts, sports, all)
        location: Location filter (e.g., 'athens', 'amsterdam', 'paris') - filters by city name in address
        start_date: Event start date in YYYY-MM-DD format (optional, defaults to today)
        end_date: Event end date in YYYY-MM-DD format (optional, defaults to start_date + days_ahead)
        days_ahead: Number of days ahead if start_date/end_date not provided (default: 30)

    Returns:
        Formatted string with event listings including titles, dates, venues, music types, and URLs
    """
    try:
        # Parse date range
        if start_date is None:
            event_start = datetime.now()
        else:
            event_start = datetime.strptime(start_date, "%Y-%m-%d")

        if end_date is None:
            event_end = event_start + timedelta(days=days_ahead)
        else:
            event_end = datetime.strptime(end_date, "%Y-%m-%d")

        # Set end time to end of day to include all events on the last day
        event_end = event_end.replace(hour=23, minute=59, second=59)

        print(f"[*] Fetching GO-OUT events for category: {category}")
        print(f"[*] Date range: {event_start.strftime('%Y-%m-%d')} to {event_end.strftime('%Y-%m-%d')}\n")

        # API endpoint
        url = "https://www.go-out.co/endOne/getEventsByTypeNew?"

        # Request payload - Types mapping for different categories
        category_types = {
            "nightlife": ["אירועים", "מועדוני לילה"],  # Events + Nightclubs
            "concerts": ["קונצרטים"],  # Concerts
            "sports": ["ספורט"],  # Sports
            "all": ["אירועים", "מועדוני לילה", "קונצרטים", "ספורט"]
        }

        payload = {
            "skip": 0,
            "Types": category_types.get(category, ["אירועים", "מועדוני לילה"]),
            "limit": 100,
            "recivedDate": datetime.now().isoformat() + "Z",
            "location": {}
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://www.go-out.co/tickets/{category}",
            "Origin": "https://www.go-out.co"
        }

        # Make request
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code != 200:
            return f"❌ API request failed with status {response.status_code}"

        data = response.json()

        if not data.get('status'):
            return f"❌ API returned error status"

        all_events = data.get('events', [])

        if not all_events:
            return f"No events found for {category}"

        # Filter events by date
        filtered_events = []
        for event in all_events:
            try:
                event_date = datetime.fromisoformat(event['StartingDate'].replace('Z', ''))
                if event_start <= event_date <= event_end:
                    filtered_events.append(event)
            except:
                filtered_events.append(event)

        if not filtered_events:
            return f"No events found in {category} between {event_start.strftime('%Y-%m-%d')} and {event_end.strftime('%Y-%m-%d')}"

        # Filter by location if specified
        if location:
            # Map common city name variations (e.g., Athens -> Athina)
            location_variants = {
                'athens': ['athens', 'athina', 'αθήνα'],
                'thessaloniki': ['thessaloniki', 'θεσσαλονίκη', 'salonika'],
            }

            search_terms = location_variants.get(location.lower(), [location.lower()])

            location_filtered = []
            for event in filtered_events:
                address = event.get('EnglishAddress', '').lower()
                # Check if any of the search terms match
                if any(term in address for term in search_terms):
                    location_filtered.append(event)
            filtered_events = location_filtered

            if not filtered_events:
                return f"No events found in {location}"

        # Format output
        result = f"🎉 GO-OUT {category.title()} Events ({len(filtered_events)} events)\n"
        result += f"📅 Date range: {event_start.strftime('%Y-%m-%d')} to {event_end.strftime('%Y-%m-%d')}\n\n"

        for idx, event in enumerate(filtered_events[:20], 1):
            title = event.get('Title', 'Untitled')
            address = event.get('EnglishAddress', event.get('Adress', 'Address TBA'))

            try:
                start_dt = datetime.fromisoformat(event['StartingDate'].replace('Z', ''))
                date_str = start_dt.strftime('%Y-%m-%d at %H:%M')
            except:
                full_date = event.get('FullDate', {}).get('starting', {})
                date_info = full_date.get('date', {})
                time_info = full_date.get('time', {})
                date_str = f"{date_info.get('year', '')}-{date_info.get('month', '').zfill(2)}-{date_info.get('day', '').zfill(2)}"
                if time_info:
                    date_str += f" at {time_info.get('hours', '').zfill(2)}:{time_info.get('minutes', '').zfill(2)}"

            event_url = f"https://www.go-out.co/event/{event.get('Url', event.get('_id', ''))}"

            # Get music types (remove nulls)
            music_types = event.get('MusicType', [])
            music_types = [m for m in music_types if m] if music_types else []

            result += f"{idx}. {title}\n"
            result += f"   📍 {address}\n"
            result += f"   📅 {date_str}\n"
            if music_types:
                result += f"   🎵 {', '.join(music_types[:3])}\n"
            result += f"   🔗 {event_url}\n\n"

        result += f"\n✅ Found {len(filtered_events)} events. Visit go-out.co for complete details."
        return result

    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"
    except Exception as e:
        return f"❌ Error fetching GO-OUT events: {str(e)}"


@tool
def fetch_ra_events(location: str = "greece", start_date: str = None, end_date: str = None, days_ahead: int = 30) -> str:
    """
    Fetch real electronic music event data from Resident Advisor using their GraphQL API.

    Args:
        location: Location name (e.g., 'greece', 'athens', 'berlin', 'london', 'newyork')
        start_date: Event start date in YYYY-MM-DD format (optional, defaults to today)
        end_date: Event end date in YYYY-MM-DD format (optional, defaults to start_date + days_ahead)
        days_ahead: Number of days ahead if start_date/end_date not provided (default: 30)

    Returns:
        Formatted string with actual event listings including titles, dates, venues, and URLs
    """
    try:
        # Get area ID
        area_id = AREA_IDS.get(location.lower())
        if not area_id:
            return f"❌ Unknown location: {location}. Available: {', '.join(AREA_IDS.keys())}"

        # Parse date range
        if start_date is None:
            event_start = datetime.now().strftime("%Y-%m-%d")
        else:
            event_start = start_date

        if end_date is None:
            event_end = (datetime.strptime(event_start, "%Y-%m-%d") + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        else:
            event_end = end_date

        # For listingDate filter: fetch events listed in wider window
        listing_start = datetime.now().strftime("%Y-%m-%d")
        listing_end = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

        print(f"[*] Fetching RA events via GraphQL API for {location} (area_id: {area_id})")
        print(f"[*] Filtering events happening between: {event_start} and {event_end}")

        # GraphQL query
        graphql_query = """
        query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int) {
          eventListings(filters: $filters, filterOptions: $filterOptions, page: $page, pageSize: $pageSize) {
            data {
              id
              listingDate
              event {
                id
                title
                date
                startTime
                endTime
                contentUrl
                flyerFront
                attending
                venue {
                  id
                  name
                  contentUrl
                }
              }
            }
            totalResults
          }
        }
        """

        # Variables - use listingDate to fetch broadly, then filter by actual event date
        variables = {
            "filters": {
                "areas": {"eq": area_id},
                "listingDate": {
                    "gte": listing_start,
                    "lte": listing_end
                }
            },
            "filterOptions": {"genre": True},
            "pageSize": 100,  # Max allowed by API
            "page": 1
        }

        # Make request
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.post(
            "https://ra.co/graphql",
            json={"query": graphql_query, "variables": variables},
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return f"❌ API request failed with status {response.status_code}"

        data = response.json()

        # Parse results
        if "errors" in data:
            return f"❌ GraphQL errors: {data['errors']}"

        all_events = data.get("data", {}).get("eventListings", {}).get("data", [])

        # Filter events by actual event date (not listing date)
        filtered_events = []
        for listing in all_events:
            event = listing.get("event", {})
            event_date_str = event.get("date", "")[:10]  # Get YYYY-MM-DD

            # Check if event date is within requested range
            if event_start <= event_date_str <= event_end:
                filtered_events.append(listing)

        if not filtered_events:
            return f"❌ No events found in {location} between {event_start} and {event_end}."

        # Format output
        result = f"🎵 Events in {location.title()} ({len(filtered_events)} events found)\n"
        result += f"📅 Date range: {event_start} to {event_end}\n\n"

        for idx, listing in enumerate(filtered_events, 1):
            event = listing.get("event", {})
            title = event.get("title", "Untitled")
            date = event.get("date", "TBA")
            start_time = event.get("startTime", "")
            venue_info = event.get("venue", {})
            venue_name = venue_info.get("name", "Unknown Venue")
            event_url = f"https://ra.co{event.get('contentUrl', '')}"
            attending = event.get("attending", 0)

            result += f"{idx}. {title}\n"
            result += f"   📍 {venue_name}\n"
            result += f"   📅 {date[:10]}"  # Just the date part
            if start_time:
                result += f" at {start_time[11:16]}"  # Extract time HH:MM
            result += f"\n"
            result += f"   👥 {attending} attending\n"
            result += f"   🔗 {event_url}\n\n"

        result += f"\n✅ Found {len(filtered_events)} events. Visit ra.co for complete details."
        return result

    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"
    except Exception as e:
        return f"❌ Error fetching RA events: {str(e)}"


def create_agent(llm: ChatOpenAI, tools: list, system_prompt: str):
    """Create a function-calling agent"""
    system_prompt += (
        "\nWork autonomously according to your specialty, using the tools available to you."
        " Do not ask for clarification."
    )
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_openai_functions_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True)
    return executor


def create_team_supervisor(llm: ChatOpenAI, system_prompt: str, members: list):
    """An LLM-based router"""
    options = ["FINISH"] + members
    function_def = {
        "name": "route",
        "description": "Select the next role.",
        "parameters": {
            "title": "routeSchema",
            "type": "object",
            "properties": {
                "next": {
                    "title": "Next",
                    "anyOf": [{"enum": options}],
                },
            },
            "required": ["next"],
        },
    }
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("system", "Given the conversation above, who should act next?" " Or should we FINISH? Select one of: {options}"),
        ]
    ).partial(options=str(options), team_members=", ".join(members))
    
    return (
        prompt
        | llm.bind_functions(functions=[function_def], function_call="route")
        | JsonOutputFunctionsParser()
    )


def agent_node(state: AgentState, agent, name: str):
    """Execute an agent and return its result"""
    result = agent.invoke(state)
    return {
        "messages": [HumanMessage(content=result["output"], name=name)]
    }


async def build_graph():
    """Build the multi-agent graph - ALWAYS calls both RA and GO-OUT for every query"""

    # Create separate agents
    ra_agent = create_agent(
        model,
        [fetch_ra_events],
        """You are a Resident Advisor events specialist. Fetch electronic music events using fetch_ra_events.

        Supported locations: greece, athens, berlin, london, newyork, amsterdam

        Always use custom date ranges if the user specifies dates:
        - Use start_date and end_date parameters in YYYY-MM-DD format
        - Examples: "events Nov 1-5" → start_date="2025-11-01", end_date="2025-11-05"

        Provide event listings with titles, dates, venues, attendance, and direct URLs."""
    )

    goout_agent = create_agent(
        model,
        [fetch_goout_events],
        """You are a GO-OUT events specialist. Fetch nightlife, concerts, and sports events using fetch_goout_events.

        Categories: nightlife, concerts, sports, all
        Location filtering: athens, amsterdam, paris, toronto, etc. (searches in address)

        Always use custom date ranges if the user specifies dates:
        - Use start_date and end_date parameters in YYYY-MM-DD format
        - Examples: "nightlife in Athens Nov 1-5" → category="nightlife", location="athens", start_date="2025-11-01", end_date="2025-11-05"

        Provide event listings with titles, dates, venues, music types, and direct URLs."""
    )

    ra_node = functools.partial(agent_node, agent=ra_agent, name="RAEvents")
    goout_node = functools.partial(agent_node, agent=goout_agent, name="GOOUTEvents")

    # Simple graph: Query → RA → GO-OUT → END (both always execute)
    graph = StateGraph(AgentState)

    graph.add_node("RAEvents", ra_node)
    graph.add_node("GOOUTEvents", goout_node)

    # Set entry point and create sequential chain
    graph.set_entry_point("RAEvents")
    graph.add_edge("RAEvents", "GOOUTEvents")
    graph.add_edge("GOOUTEvents", END)

    return graph.compile()


async def run_query(graph, query: str):
    """Run a single query through the multi-agent graph"""
    print(f"\n{'='*60}")
    print(f"[>] Query: {query}")
    print(f"{'='*60}\n")

    result = await graph.ainvoke({"messages": [HumanMessage(content=query)]})

    # Show results from BOTH agents (skip the initial user message)
    agent_messages = [msg for msg in result["messages"][1:] if hasattr(msg, 'name')]

    print(f"[<] Combined Results from Both Platforms:\n")
    print("="*60)

    for msg in agent_messages:
        agent_name = msg.name if hasattr(msg, 'name') else "Unknown"
        print(f"\n--- {agent_name} ---\n")

        # Handle encoding issues on Windows console
        try:
            print(msg.content)
        except UnicodeEncodeError:
            # Fallback: encode with errors='replace' for console compatibility
            print(msg.content.encode('ascii', 'replace').decode('ascii'))

    print("\n" + "="*60 + "\n")


async def main():
    """Main execution"""
    print("[*] Building multi-agent graph...")
    graph = await build_graph()

    # Both agents will ALWAYS execute for every query
    await run_query(graph, "What events are happening in Athens between November 1st and November 5th, 2025?")


if __name__ == "__main__":
    asyncio.run(main())
