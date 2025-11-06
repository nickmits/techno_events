"""
Tool result parsing utilities for web fetch results
"""
from typing import List, Dict, Any
from langchain_core.messages import ToolMessage
import logging

logger = logging.getLogger(__name__)


def parse_tool_messages(tool_messages: List[ToolMessage], user_query: str) -> List[Dict[str, Any]]:
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
        events = parse_web_results_to_structured(tool_msg.content, source_name)
        all_results.extend(events)
        logger.info(f"  - {source_name}: {len(events)} events parsed")

    return all_results


def parse_web_results_to_structured(content: str, source: str) -> List[Dict[str, Any]]:
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


def parse_tavily_results(results: str, query: str) -> List[Dict[str, Any]]:
    """
    Parse Tavily search results into event-like format
    """
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
