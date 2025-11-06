"""
Tavily Web Search Tool for Events
Fallback web search when RA/GO-OUT don't return results
"""

from langchain_community.tools.tavily_search import TavilySearchResults
import os


def get_tavily_search_tool(max_results: int = 5):
    """
    Get Tavily search tool configured for event searches.

    Args:
        max_results: Maximum number of search results to return

    Returns:
        TavilySearchResults tool instance
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")

    if not tavily_api_key:
        raise ValueError("TAVILY_API_KEY environment variable is required for web search")

    return TavilySearchResults(
        max_results=max_results,
        search_depth="advanced",
        include_answer=True,
        include_raw_content=False,
        api_key=tavily_api_key
    )
