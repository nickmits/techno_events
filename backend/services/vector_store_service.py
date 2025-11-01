"""
Vector Store Service - Manages Qdrant vector store for event caching and retrieval
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from langchain_openai import OpenAIEmbeddings
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import os
import json
import csv
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing event storage and retrieval in Qdrant vector store"""

    def __init__(self, path: str = "./data/qdrant_storage", collection_name: str = "techno_events"):
        """Initialize the vector store service"""
        self.embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
        self.collection_name = collection_name
        self.storage_path = path
        self.csv_path = "./data/events_with_metadata.csv"

        # Create data directory if it doesn't exist
        Path("./data").mkdir(exist_ok=True)

        # Use persistent local Qdrant
        self.client = QdrantClient(path=path)
        self.initialized = False
        self.vector_size = 1536  # text-embedding-3-small dimension

        logger.info(f"VectorStoreService created with persistent storage at {path}")

    def check_events_exist(self, start_date: str, end_date: str, location: Optional[str] = None) -> bool:
        """
        Check if events for a given date range and location exist in vector store

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            location: Optional location filter

        Returns:
            True if events exist, False otherwise
        """
        if not self.initialized:
            logger.info("Vector store not initialized yet, no events exist")
            return False

        try:
            # Build filter conditions
            conditions = [
                FieldCondition(key="start_date", match=MatchValue(value=start_date)),
                FieldCondition(key="end_date", match=MatchValue(value=end_date))
            ]

            if location:
                conditions.append(
                    FieldCondition(key="location", match=MatchValue(value=location.lower()))
                )

            search_filter = Filter(must=conditions)

            # Create a dummy query embedding
            query_embedding = self.embedding_model.embed_query(f"events from {start_date} to {end_date}")

            # Search with filter
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=1
            )

            exists = len(results) > 0
            logger.info(f"Events exist check for {start_date} to {end_date}: {exists}")
            return exists

        except Exception as e:
            logger.error(f"Error checking if events exist: {e}")
            return False

    def store_events(
        self,
        events_data: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        location: Optional[str] = None
    ):
        """
        Store events in vector store and export to CSV

        Args:
            events_data: List of event dictionaries from sources
            start_date: Start date of query
            end_date: End date of query
            location: Location filter used
        """
        try:
            # Parse all events from content
            all_events = []
            for event_data in events_data:
                source_name = event_data.get("name", "Unknown")
                content = event_data.get("content", "")

                # Parse individual events from the content string
                events = self._parse_events_from_content(content, source_name)

                for event in events:
                    event_record = {
                        "event_id": f"{source_name}_{len(all_events)}",
                        "title": event.get("title", ""),
                        "description": event.get("text", ""),
                        "venue": event.get("venue", ""),
                        "event_date": event.get("date", ""),
                        "url": event.get("url", ""),
                        "source": source_name,
                        "location": location.lower() if location else "",
                        "start_date": start_date,
                        "end_date": end_date,
                        "attending": event.get("attending", ""),
                        "music_types": event.get("music_types", ""),
                        "stored_at": datetime.now().isoformat()
                    }
                    all_events.append(event_record)

            if not all_events:
                logger.warning("No events to store")
                return

            # Initialize collection on first use
            if not self.initialized:
                logger.info(f"Initializing Qdrant collection...")
                try:
                    self.client.delete_collection(self.collection_name)
                except:
                    pass

                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                self.initialized = True
                logger.info(f"Qdrant collection '{self.collection_name}' created")

            # Create embeddings and points
            points = []
            for idx, event in enumerate(all_events):
                # Create text for embedding
                embedding_text = f"{event['title']} {event['description']} {event['venue']}"

                # Create embedding
                embedding = self.embedding_model.embed_query(embedding_text)

                # Create point
                point = PointStruct(
                    id=idx,
                    vector=embedding,
                    payload=event
                )
                points.append(point)

            # Upload to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Stored {len(points)} events in Qdrant")

            # Export to CSV
            self._export_to_csv(all_events)

        except Exception as e:
            logger.error(f"Error storing events: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _parse_events_from_content(self, content: str, source: str) -> List[Dict[str, str]]:
        """
        Parse individual events from formatted content string

        Args:
            content: Formatted event listings string
            source: Source name (RAEvents, GOOUTEvents)

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            # Split by numbered events (e.g., "1. ", "2. ")
            lines = content.split('\n')
            current_event = {}
            current_text = []

            for line in lines:
                line = line.strip()

                # Check if this is the start of a new event (numbered line)
                if line and line[0].isdigit() and '. ' in line[:5]:
                    # Save previous event if exists
                    if current_event:
                        current_event["text"] = '\n'.join(current_text)
                        events.append(current_event)

                    # Start new event
                    current_event = {"title": line.split('. ', 1)[1] if '. ' in line else line}
                    current_text = [line]

                elif line and current_event:
                    current_text.append(line)

                    # Extract metadata
                    if '📍' in line:
                        current_event["venue"] = line.replace('📍', '').strip()
                    elif '📅' in line:
                        # Extract date from line like "📅 2025-11-01 at 23:59"
                        date_part = line.replace('📅', '').strip()
                        if date_part:
                            current_event["date"] = date_part.split(' ')[0]  # Get YYYY-MM-DD part
                    elif '👥' in line:
                        # Extract attending count
                        current_event["attending"] = line.replace('👥', '').replace('attending', '').strip()
                    elif '🎵' in line:
                        # Extract music types
                        current_event["music_types"] = line.replace('🎵', '').strip()
                    elif '🔗' in line:
                        current_event["url"] = line.replace('🔗', '').strip()

            # Add last event
            if current_event:
                current_event["text"] = '\n'.join(current_text)
                events.append(current_event)

        except Exception as e:
            logger.error(f"Error parsing events from content: {e}")

        return events

    def _export_to_csv(self, events: List[Dict[str, Any]]):
        """Export events to CSV file with all metadata"""
        try:
            # Define CSV fieldnames
            fieldnames = [
                "event_id", "title", "description", "venue", "event_date",
                "url", "source", "location", "start_date", "end_date",
                "attending", "music_types", "stored_at"
            ]

            # Check if file exists to determine if we need to write headers
            file_exists = Path(self.csv_path).exists()

            # Write to CSV (append mode)
            with open(self.csv_path, mode='a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Write header if file doesn't exist
                if not file_exists:
                    writer.writeheader()

                # Write events
                for event in events:
                    writer.writerow(event)

            logger.info(f"Exported {len(events)} events to CSV: {self.csv_path}")

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def retrieve_events(self, query: str, k: int = 20) -> str:
        """
        Retrieve events from vector store based on semantic search

        Args:
            query: User query
            k: Number of results to return

        Returns:
            Formatted string with retrieved events
        """
        if not self.initialized:
            logger.warning("Vector store not initialized, no events to retrieve")
            return "No events found in cache. Please fetch events first."

        try:
            # Create query embedding
            query_embedding = self.embedding_model.embed_query(query)

            # Search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=k
            )

            if not results:
                return "No events found in stored data"

            # Group by source
            ra_events = []
            goout_events = []

            for result in results:
                payload = result.payload
                source = payload.get("source", "")

                # Reconstruct event text
                event_text = f"{payload.get('title', '')}\n"
                event_text += f"📍 {payload.get('venue', '')}\n"
                event_text += f"📅 {payload.get('event_date', '')}\n"

                if payload.get('attending'):
                    event_text += f"👥 {payload.get('attending', '')}\n"

                if payload.get('music_types'):
                    event_text += f"🎵 {payload.get('music_types', '')}\n"

                event_text += f"🔗 {payload.get('url', '')}"

                if "RA" in source:
                    ra_events.append(event_text)
                else:
                    goout_events.append(event_text)

            # Format response
            response = ""

            if ra_events:
                response += f"🎵 Resident Advisor Events ({len(ra_events)} events from stored data)\n\n"
                response += '\n\n'.join(ra_events)
                response += "\n✅ Found {} events. Visit ra.co for complete details.\n\n".format(len(ra_events))

            if goout_events:
                response += f"🎉 GO-OUT Events ({len(goout_events)} events from stored data)\n\n"
                response += '\n\n'.join(goout_events)
                response += "\n✅ Found {} events. Visit go-out.co for complete details.\n".format(len(goout_events))

            return response

        except Exception as e:
            logger.error(f"Error retrieving events: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Error retrieving events: {str(e)}"
