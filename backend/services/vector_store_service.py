"""
Vector Store Service - CSV-first event storage with semantic retrieval
Similar to book system: uses CSV as primary source with advanced retrieval
Includes embedding caching to reduce API calls
"""

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain.retrievers import EnsembleRetriever, MultiQueryRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain.chat_models import init_chat_model
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import os
import csv
from pathlib import Path
import pandas as pd
import hashlib
import json

logger = logging.getLogger(__name__)


class CachedEmbeddings(Embeddings):
    """Wrapper around OpenAIEmbeddings with caching support - inherits from Embeddings base class"""

    def __init__(self, embedding_model: OpenAIEmbeddings, vector_store_service):
        self.embedding_model = embedding_model
        self.vector_store = vector_store_service
        self.cache_hits = 0
        self.cache_misses = 0

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents with caching"""
        embeddings = []
        texts_to_embed = []
        text_indices = []

        # Check cache for each text
        for i, text in enumerate(texts):
            cached = self.vector_store._get_cached_embedding(text)
            if cached is not None:
                embeddings.append(cached)
                self.cache_hits += 1
            else:
                texts_to_embed.append(text)
                text_indices.append(i)
                embeddings.append(None)  # Placeholder
                self.cache_misses += 1

        # Embed texts that weren't cached
        if texts_to_embed:
            logger.info(f"📊 Embedding cache: {self.cache_hits} hits, {self.cache_misses} misses ({self.cache_hits / (self.cache_hits + self.cache_misses) * 100:.1f}% hit rate)")
            new_embeddings = self.embedding_model.embed_documents(texts_to_embed)

            # Cache new embeddings and fill in placeholders
            for idx, text, embedding in zip(text_indices, texts_to_embed, new_embeddings):
                self.vector_store._cache_embedding(text, embedding)
                embeddings[idx] = embedding

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed query with caching"""
        cached = self.vector_store._get_cached_embedding(text)
        if cached is not None:
            self.cache_hits += 1
            logger.info(f"✅ Using cached embedding for query")
            return cached

        self.cache_misses += 1
        logger.info(f"⚠️ Cache miss, generating new embedding")
        embedding = self.embedding_model.embed_query(text)
        self.vector_store._cache_embedding(text, embedding)

        # Save cache periodically (every 10 misses)
        if self.cache_misses % 10 == 0:
            self.vector_store._save_embedding_cache()

        return embedding


class VectorStoreService:
    """Service for managing event storage and retrieval from CSV with semantic search"""

    def __init__(self, csv_path: str = "./backend/data/events_with_metadata.csv"):
        """Initialize the vector store service with CSV as primary source"""
        self.csv_path = csv_path
        self.embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
        self.retriever = None
        self.events_df = None

        # Embedding cache - stores {text_hash: embedding_vector}
        self.embedding_cache = {}
        self.cache_file = "./backend/data/embedding_cache.json"
        self._load_embedding_cache()

        # Create data directory if it doesn't exist
        Path("./data").mkdir(exist_ok=True)

        # Initialize CSV file with headers if it doesn't exist
        if not Path(self.csv_path).exists():
            self._initialize_csv()
            logger.info(f"Created new CSV file at {self.csv_path}")
        else:
            logger.info(f"Using existing CSV file at {self.csv_path}")

        # Load CSV data and build retriever
        self._load_and_build_retriever()

    def _load_embedding_cache(self):
        """Load embedding cache from disk"""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.embedding_cache = json.load(f)
                logger.info(f"Loaded {len(self.embedding_cache)} cached embeddings")
            else:
                self.embedding_cache = {}
                logger.info("No embedding cache found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading embedding cache: {e}")
            self.embedding_cache = {}

    def _save_embedding_cache(self):
        """Save embedding cache to disk"""
        try:
            Path("./backend/data").mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.embedding_cache, f)
            logger.info(f"Saved {len(self.embedding_cache)} embeddings to cache")
        except Exception as e:
            logger.error(f"Error saving embedding cache: {e}")

    def _get_text_hash(self, text: str) -> str:
        """Generate a hash for text to use as cache key"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache if exists"""
        text_hash = self._get_text_hash(text)
        return self.embedding_cache.get(text_hash)

    def _cache_embedding(self, text: str, embedding: List[float]):
        """Cache an embedding"""
        text_hash = self._get_text_hash(text)
        self.embedding_cache[text_hash] = embedding

    def _initialize_csv(self):
        """Create CSV file with proper headers"""
        fieldnames = [
            "event_id", "title", "description", "venue", "event_date",
            "url", "source", "location", "start_date", "end_date",
            "attending", "music_types", "venue_lat", "venue_lon", "stored_at"
        ]

        with open(self.csv_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

    def _load_and_build_retriever(self):
        """Load CSV data and build semantic retriever (like book system)"""
        try:
            # Check if CSV has data
            if not Path(self.csv_path).exists() or os.path.getsize(self.csv_path) <= 100:
                logger.info("CSV is empty or doesn't exist. Retriever will be built after first data fetch.")
                self.events_df = pd.DataFrame()
                self.retriever = None
                return

            # Load CSV with error handling for corrupted lines
            self.events_df = pd.read_csv(self.csv_path, on_bad_lines='skip')

            if len(self.events_df) == 0:
                logger.info("CSV has no events yet. Retriever will be built after first data fetch.")
                self.retriever = None
                return

            logger.info(f"Loaded {len(self.events_df)} events from CSV")

            # Convert to LangChain documents
            documents = []
            for idx, row in self.events_df.iterrows():
                # Create rich text content for embedding
                event_text = f"""Event: {row['title']}
Venue: {row['venue']}
Date: {row['event_date']}
Description: {row['description']}
Music Types: {row.get('music_types', '')}
Location: {row['location']}
"""

                metadata = {
                    "event_id": row['event_id'],
                    "title": row['title'],
                    "venue": row['venue'],
                    "event_date": row['event_date'],
                    "url": row['url'],
                    "source": row['source'],
                    "location": row['location'],
                    "start_date": row['start_date'],
                    "end_date": row['end_date'],
                    "attending": row.get('attending', ''),
                    "music_types": row.get('music_types', ''),
                    "row_index": idx
                }

                doc = Document(page_content=event_text.strip(), metadata=metadata)
                documents.append(doc)

            # Build ensemble retriever (BM25 + Semantic + Multi-Query)
            self._build_ensemble_retriever(documents)

            logger.info(f"Built retriever with {len(documents)} event documents")

        except Exception as e:
            logger.error(f"Error loading CSV and building retriever: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.retriever = None

    def _build_ensemble_retriever(self, documents: List[Document]):
        """Build sophisticated ensemble retriever like book system"""
        try:
            # Get API key
            openai_api_key = os.getenv("OPENAI_API_KEY")
            cohere_api_key = os.getenv("COHERE_API_KEY")

            if not openai_api_key:
                logger.warning("OPENAI_API_KEY not found, using basic retrieval")
                self.retriever = None
                return

            # Initialize chat model for multi-query
            chat_model = init_chat_model(
                model="openai:gpt-4o-mini",
                api_key=openai_api_key,
                temperature=0.1,
                max_tokens=1000
            )

            # 1. BM25 Retriever (keyword-based)
            bm25_retriever = BM25Retriever.from_documents(documents)
            bm25_retriever.k = 100  # Increased from 10 to get more results

            # 2. Semantic Vector Store with cached embeddings
            cached_embeddings = CachedEmbeddings(self.embedding_model, self)

            # Use Qdrant Cloud if credentials are available, otherwise use in-memory
            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")

            if qdrant_url and qdrant_api_key:
                logger.info(f"Using Qdrant Cloud at {qdrant_url}")
                vectorstore = Qdrant.from_documents(
                    documents=documents,
                    embedding=cached_embeddings,
                    url=qdrant_url,
                    api_key=qdrant_api_key,
                    collection_name="events_semantic",
                    prefer_grpc=True
                )
            else:
                logger.info("Using in-memory Qdrant")
                vectorstore = Qdrant.from_documents(
                    documents=documents,
                    embedding=cached_embeddings,
                    location=":memory:",
                    collection_name="events_semantic"
                )

            # Save cache after building vector store
            self._save_embedding_cache()

            # 3. Multi-Query Retriever (generates multiple search queries)
            multi_query_retriever = MultiQueryRetriever.from_llm(
                retriever=vectorstore.as_retriever(search_kwargs={"k": 100}),  # Increased from 15
                llm=chat_model
            )

            # 4. Optional: Cohere Reranking
            if cohere_api_key:
                try:
                    from langchain_cohere import CohereRerank

                    compression_retriever = ContextualCompressionRetriever(
                        base_retriever=multi_query_retriever,
                        base_compressor=CohereRerank(model="rerank-v3.5", cohere_api_key=cohere_api_key)
                    )

                    # Ensemble with reranking
                    self.retriever = EnsembleRetriever(
                        retrievers=[bm25_retriever, multi_query_retriever, compression_retriever],
                        weights=[0.3, 0.3, 0.4]
                    )
                    logger.info("Built ensemble retriever WITH Cohere reranking")
                except ImportError:
                    logger.warning("Cohere not available, using ensemble without reranking")
                    self.retriever = EnsembleRetriever(
                        retrievers=[bm25_retriever, multi_query_retriever],
                        weights=[0.4, 0.6]
                    )
            else:
                # Ensemble without reranking
                self.retriever = EnsembleRetriever(
                    retrievers=[bm25_retriever, multi_query_retriever],
                    weights=[0.4, 0.6]
                )
                logger.info("Built ensemble retriever WITHOUT reranking")

        except Exception as e:
            logger.error(f"Error building ensemble retriever: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.retriever = None

    def check_events_exist(self, start_date: str, end_date: str, location: Optional[str] = None) -> bool:
        """
        Check if events for a given date range and location exist in CSV

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            location: Optional location filter

        Returns:
            True if events exist, False otherwise
        """
        try:
            if self.events_df is None or len(self.events_df) == 0:
                logger.info("CSV is empty, no events exist")
                return False

            # Filter by date range
            mask = (self.events_df['start_date'] == start_date) & (self.events_df['end_date'] == end_date)

            # Add location filter if provided
            if location:
                mask = mask & (self.events_df['location'].str.lower() == location.lower())

            matching_events = self.events_df[mask]
            exists = len(matching_events) > 0

            logger.info(f"Events exist check for {start_date} to {end_date} (location: {location}): {exists} ({len(matching_events)} events)")
            return exists

        except Exception as e:
            logger.error(f"Error checking if events exist in CSV: {e}")
            return False

    def _create_event_key(self, title: str, event_date: str, url: str) -> str:
        """Create a unique key for an event based on title, date, and URL"""
        # Normalize title (lowercase, strip whitespace)
        normalized_title = title.lower().strip()
        # Use URL as primary key if available, otherwise use title+date
        if url:
            return url.strip().lower()
        return f"{normalized_title}|{event_date}"

    def _get_existing_event_keys(self) -> set:
        """Get set of existing event keys from CSV"""
        existing_keys = set()
        try:
            if self.events_df is not None and len(self.events_df) > 0:
                for _, row in self.events_df.iterrows():
                    key = self._create_event_key(
                        row.get('title', ''),
                        row.get('event_date', ''),
                        row.get('url', '')
                    )
                    existing_keys.add(key)
        except Exception as e:
            logger.error(f"Error getting existing event keys: {e}")
        return existing_keys

    def store_events(
        self,
        events_data: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        location: Optional[str] = None
    ):
        """
        Store events in CSV and rebuild retriever (with duplicate detection)

        Args:
            events_data: List of event dictionaries from sources
            start_date: Start date of query
            end_date: End date of query
            location: Location filter used
        """
        try:
            # Get existing event keys to prevent duplicates
            existing_keys = self._get_existing_event_keys()
            logger.info(f"Found {len(existing_keys)} existing events in CSV")

            # Parse all events from content
            all_events = []
            duplicates_skipped = 0

            for event_data in events_data:
                source_name = event_data.get("name", "Unknown")
                content = event_data.get("content", "")

                # Parse individual events from the content string
                events = self._parse_events_from_content(content, source_name)

                for event in events:
                    # Create event key for duplicate checking
                    event_key = self._create_event_key(
                        event.get("title", ""),
                        event.get("date", ""),
                        event.get("url", "")
                    )

                    # Skip if event already exists
                    if event_key in existing_keys:
                        duplicates_skipped += 1
                        logger.debug(f"⏭️ Skipping duplicate event: {event.get('title')} on {event.get('date')}")
                        continue

                    # Clean description to prevent CSV corruption
                    description = event.get("text", "")
                    if description:
                        description = description.replace('\n', ' ').replace('\r', ' ')

                    event_record = {
                        "event_id": f"{source_name}_{len(all_events)}_{datetime.now().timestamp()}",
                        "title": event.get("title", ""),
                        "description": description,
                        "venue": event.get("venue", ""),
                        "event_date": event.get("date", ""),
                        "url": event.get("url", ""),
                        "source": source_name,
                        "location": location.lower() if location else "",
                        "start_date": start_date,
                        "end_date": end_date,
                        "attending": event.get("attending", ""),
                        "music_types": event.get("music_types", ""),
                        "venue_lat": event.get("venue_lat", ""),
                        "venue_lon": event.get("venue_lon", ""),
                        "stored_at": datetime.now().isoformat()
                    }
                    all_events.append(event_record)
                    # Add to existing keys to prevent duplicates within this batch
                    existing_keys.add(event_key)

            if duplicates_skipped > 0:
                logger.info(f"⏭️ Skipped {duplicates_skipped} duplicate events")

            if not all_events:
                logger.warning("No new events to store (all were duplicates or empty)")
                return

            # Append to CSV
            self._append_to_csv(all_events)

            # Reload CSV and rebuild retriever
            logger.info("Rebuilding retriever with new events...")
            self._load_and_build_retriever()

            logger.info(f"Successfully stored {len(all_events)} new events and rebuilt retriever")

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
        logger.info(f"🔵 _parse_events_from_content called for {source}, content length: {len(content)}")
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

            logger.info(f"🟢 Before cleaning: {len(events)} events parsed")
            # Clean descriptions to prevent CSV corruption
            for event in events:
                if "text" in event:
                    original = event["text"]
                    # Replace newlines with spaces to avoid breaking CSV format
                    event["text"] = event["text"].replace('\n', ' ').replace('\r', ' ')
                    logger.info(f"🧹 Cleaned description: {len(original)} chars → {len(event['text'])} chars (had newlines: {chr(10) in original})")

        except Exception as e:
            logger.error(f"Error parsing events from content: {e}")

        return events

    def _append_to_csv(self, events: List[Dict[str, Any]]):
        """Append events to CSV file"""
        try:
            fieldnames = [
                "event_id", "title", "description", "venue", "event_date",
                "url", "source", "location", "start_date", "end_date",
                "attending", "music_types", "venue_lat", "venue_lon", "stored_at"
            ]

            # Append to CSV
            with open(self.csv_path, mode='a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Write events
                for event in events:
                    writer.writerow(event)

            logger.info(f"Appended {len(events)} events to CSV: {self.csv_path}")

        except Exception as e:
            logger.error(f"Error appending to CSV: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def retrieve_events(
        self,
        query: str,
        k: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve events from CSV using semantic search

        Args:
            query: User query
            k: Number of results to return
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            location: Optional location filter

        Returns:
            List of event dictionaries with all metadata
        """
        if self.retriever is None:
            logger.warning("Retriever not initialized, no events to retrieve")
            return []

        try:
            # Use retriever to get relevant documents
            results = self.retriever.get_relevant_documents(query)

            # Filter by metadata if needed - FILTER FIRST, then slice
            filtered_results = []
            for doc in results:  # Removed [:k] - filter all results first
                metadata = doc.metadata

                # Apply filters
                if start_date and metadata.get("start_date") != start_date:
                    continue
                if end_date and metadata.get("end_date") != end_date:
                    continue
                # Safe location comparison (handle NaN/float values)
                if location:
                    loc_value = metadata.get("location", "")
                    if isinstance(loc_value, str) and loc_value.lower() != location.lower():
                        continue
                    elif not isinstance(loc_value, str):
                        # Skip if location is not a string (NaN, float, etc.)
                        continue

                # Convert to dict format with all metadata
                event_dict = {
                    "title": metadata.get("title", "Unknown Title"),
                    "venue": metadata.get("venue", "TBA"),
                    "event_date": metadata.get("event_date", "TBA"),
                    "url": metadata.get("url", ""),
                    "source": metadata.get("source", "CSV"),
                    "location": metadata.get("location", ""),
                    "attending": metadata.get("attending", ""),
                    "music_types": metadata.get("music_types", ""),
                    "content": doc.page_content,
                    "event_id": metadata.get("event_id", "")
                }
                filtered_results.append(event_dict)

            # Now apply k limit after filtering
            filtered_results = filtered_results[:k]

            logger.info(f"Retrieved {len(filtered_results)} events for query: {query} (from {len(results)} total)")
            return filtered_results

        except Exception as e:
            logger.error(f"Error retrieving events: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def get_events_by_date_range(
        self,
        start_date: str,
        end_date: str,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get ALL events from CSV by date range (simple filtering, no semantic search)

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            location: Optional location filter

        Returns:
            List of all event dictionaries matching the date range
        """
        if self.events_df is None or len(self.events_df) == 0:
            logger.warning("No events in CSV")
            return []

        try:
            # Filter by event_date column
            filtered_df = self.events_df[
                (self.events_df["event_date"] >= start_date) &
                (self.events_df["event_date"] <= end_date)
            ]

            # Filter by location if specified
            if location:
                filtered_df = filtered_df[
                    filtered_df["location"].str.lower() == location.lower()
                ]

            # Convert to list of dicts
            events = []
            for _, row in filtered_df.iterrows():
                event_dict = {
                    "title": row.get("title", "Unknown Title"),
                    "venue": row.get("venue", "TBA"),
                    "event_date": row.get("event_date", "TBA"),
                    "url": row.get("url", ""),
                    "source": row.get("source", "CSV"),
                    "location": row.get("location", ""),
                    "attending": row.get("attending", ""),
                    "music_types": row.get("music_types", ""),
                    "content": row.get("description", ""),
                    "event_id": row.get("event_id", "")
                }
                events.append(event_dict)

            logger.info(f"Found {len(events)} events for date range {start_date} to {end_date}")
            return events

        except Exception as e:
            logger.error(f"Error getting events by date range: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
