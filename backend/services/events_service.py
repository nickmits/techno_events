"""
Events Service - Integrates LangGraph multi-agent system for event discovery
Refactored to use modular components
"""
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os
import logging

from backend.tools.ra_events import fetch_ra_events
from backend.tools.goout_events import fetch_goout_events
from backend.services.vector_store_service import VectorStoreService
from backend.services.geocoding_service import GeocodingService
from backend.services.graph_schemas import AgentState
from backend.services.graph_nodes import GraphNodes
from backend.services.graph_routing import GraphRouting

load_dotenv()

logger = logging.getLogger(__name__)


class EventsService:
    """Service for managing event queries through LangGraph"""

    def __init__(self):
        """Initialize the service and build the LangGraph"""
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.model = ChatOpenAI(model="gpt-4o-mini")
        self.graph = None
        self.checkpointer = MemorySaver()
        self.vector_store = VectorStoreService()
        self.geocoding_service = GeocodingService()
        self.tools = [fetch_ra_events, fetch_goout_events]

        # Initialize modular components
        self.nodes = GraphNodes(
            model=self.model,
            vector_store=self.vector_store,
            geocoding_service=self.geocoding_service,
            tools=self.tools
        )
        self.routing = GraphRouting(vector_store=self.vector_store)

        logger.info("EventsService initialized with modular components")

    async def _build_graph(self):
        """Build the multi-agent graph with human-in-the-loop for location"""
        graph = StateGraph(AgentState)

        # Create ToolNode for automatic tool execution
        tool_node = ToolNode(self.tools)

        # Add nodes using the modular GraphNodes class
        graph.add_node("ParseDates", self.nodes.parse_dates_node)
        graph.add_node("CheckCompleteness", self.nodes.check_completeness_node)
        graph.add_node("AskForLocation", self.nodes.ask_for_location_node)
        graph.add_node("CSVRetrieval", self.nodes.csv_retrieval_node)
        graph.add_node("WebAgent", self.nodes.web_agent_node)
        graph.add_node("CallTools", tool_node)
        graph.add_node("StoreEvents", self.nodes.storage_node)
        graph.add_node("SortByDistance", self.nodes.sort_by_distance_node)
        graph.add_node("GenerateResponse", self.nodes.generate_conversational_response_node)

        # Set entry point
        graph.set_entry_point("ParseDates")

        # Add edges
        graph.add_edge("ParseDates", "CheckCompleteness")

        # Conditional routing using the modular GraphRouting class
        graph.add_conditional_edges(
            "CheckCompleteness",
            self.routing.route_completeness_check,
            {
                "ask_location": "AskForLocation",
                "web": "WebAgent"
            }
        )

        graph.add_edge("AskForLocation", "WebAgent")

        graph.add_conditional_edges(
            "WebAgent",
            self.routing.route_web_agent,
            {"tools": "CallTools", "response": "GenerateResponse"}
        )

        graph.add_edge("CallTools", "StoreEvents")

        # Final edges: After storing, retrieve all events from CSV
        graph.add_edge("StoreEvents", "CSVRetrieval")
        graph.add_edge("CSVRetrieval", "SortByDistance")
        graph.add_edge("SortByDistance", "GenerateResponse")
        graph.add_edge("GenerateResponse", END)

        return graph.compile(checkpointer=self.checkpointer)

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

        Args:
            query: Natural language query
            location: Ignored - always uses Athens
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            days_ahead: Days ahead if dates not specified
            thread_id: Thread ID for checkpoint/resume (human-in-the-loop)
            resume_value: User's response when resuming from interrupt

        Returns:
            Dictionary containing messages from all agents, or interrupt payload
        """
        try:
            # Build graph if not already built
            if self.graph is None:
                logger.info("Building LangGraph...")
                self.graph = await self._build_graph()

            # ATHENS-ONLY: Always use athens
            location = "athens"

            # Configure checkpoint with thread_id
            config = {"configurable": {"thread_id": thread_id}} if thread_id else {}

            # If resuming from interrupt, provide the resume value
            if resume_value and thread_id:
                logger.info(f"🔄 Resuming thread {thread_id} with value: {resume_value}")

                # Geocode the user's location response
                user_coords = self.geocoding_service.geocode_venue(resume_value)

                if not user_coords:
                    logger.warning(f"Could not geocode location: {resume_value}, using Athens center")
                    user_lat, user_lon = 37.9838, 23.7275  # Athens center
                else:
                    user_lat, user_lon = user_coords

                logger.info(f"📍 User location: {resume_value} -> ({user_lat}, {user_lon})")

                # Update the state with location and continue execution
                # Get current state
                current_state = await self.graph.aget_state(config)

                # Update state with user location
                await self.graph.aupdate_state(
                    config,
                    {
                        "user_lat": user_lat,
                        "user_lon": user_lon,
                        "location": "athens"
                    }
                )

                # Resume execution from where it was interrupted
                result = await self.graph.ainvoke(None, config=config)
                return result

            # Build enhanced query
            enhanced_query = query
            if start_date and end_date:
                enhanced_query += f" between {start_date} and {end_date}"
            elif start_date:
                enhanced_query += f" starting from {start_date}"

            logger.info(f"Executing Athens query: {enhanced_query}")

            # Execute query through graph
            result = await self.graph.ainvoke(
                {
                    "messages": [HumanMessage(content=enhanced_query)],
                    "start_date": start_date,
                    "end_date": end_date,
                    "location": location,
                    "user_lat": None,
                    "user_lon": None,
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

            # Check if graph was interrupted
            if result.get("final_response") is None:
                logger.info(f"🛑 Graph interrupted, waiting for user input")

                interrupt_payload = {
                    "type": "location_request",
                    "message": f"Great! I found events from {result.get('start_date')} to {result.get('end_date')}. Where are you located in Athens? (e.g., Syntagma Square, Monastiraki, Exarchia)",
                    "dates": {
                        "start": result.get("start_date"),
                        "end": result.get("end_date")
                    }
                }

                result["interrupt"] = interrupt_payload
                return result

            return result

        except Exception as e:
            logger.error(f"Error in fetch_events: {str(e)}")
            raise
