"""
Events Retriever Tool
Retrieves events from Qdrant vector store
"""

from langchain_core.tools import tool


@tool
def retrieve_stored_events(query: str, max_results: int = 20) -> str:
    """
    Retrieve events from the vector store based on semantic search.
    Use this when the user is asking about events that may already be stored,
    or when asking specific questions about events.

    Args:
        query: The user's question or search query
        max_results: Maximum number of events to return (default: 20)

    Returns:
        Formatted string with retrieved event information
    """
    # This will be injected by the agent node
    # For now, return a placeholder
    return "This tool needs to be executed through the agent node with vector store access"
