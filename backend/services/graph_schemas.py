"""
Schema definitions for LangGraph state
"""
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langchain_core.messages import BaseMessage
import operator


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
