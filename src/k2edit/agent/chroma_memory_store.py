"""ChromaDB-based Memory Store for K2Edit Agentic System
Handles persistent storage of conversations, code context, and learned patterns using ChromaDB
for native vector embedding support.
"""

import asyncio
import json
import hashlib
import uuid
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from functools import partial
import multiprocessing as mp

import chromadb
from chromadb.config import Settings
from aiologger import Logger
import aiofiles

from ..utils.async_performance_utils import get_thread_pool


def _process_search_results_chunk(results_chunk: List[Tuple], max_distance: float, 
                                  quality_filter: bool = True) -> List[Dict[str, Any]]:
    """Worker function for multiprocessing search result processing."""
    processed_results = []
    
    for doc_id, document, metadata, distance in results_chunk:
        if distance > max_distance:
            continue
            
        try:
            content = json.loads(document)
        except (json.JSONDecodeError, TypeError):
            continue
        
        if quality_filter and _is_low_quality_content_static(content):
            continue
            
        processed_results.append({
            "id": doc_id,
            "content": content,
            "metadata": metadata,
            "distance": distance,
            "relevance_score": max(0, 1.0 - (distance / max_distance))
        })
    
    return processed_results


# Low-quality patterns compiled once for performance
LOW_QUALITY_PATTERNS = [
    re.compile(r'console\.log', re.IGNORECASE),
    re.compile(r'print\s*\(', re.IGNORECASE),
    re.compile(r'\b(TODO|FIXME|HACK|XXX)\b', re.IGNORECASE),
    re.compile(r'^\s*import\s+\w+\s*$', re.IGNORECASE),
    re.compile(r'^\s*from\s+\w+\s+import\s+\w+\s*$', re.IGNORECASE),
    re.compile(r'^\s*(var|let|const)\s+\w+\s*=\s*\w+\s*$', re.IGNORECASE),
    re.compile(r'\btemp\d*\b', re.IGNORECASE),
    re.compile(r'\btmp\d*\b', re.IGNORECASE),
]

def _extract_content_string(content: Any) -> str:
    """Extract string content from various content formats."""
    if isinstance(content, dict):
        if 'code' in content:
            return content['code']
        elif 'content' in content and isinstance(content['content'], dict) and 'code' in content['content']:
            return content['content']['code']
    return str(content).strip()

def _is_low_quality_content_static(content: Any) -> bool:
    """Static version of quality check for multiprocessing."""
    if not content:
        return True
        
    content_str = _extract_content_string(content)
    
    # Check for very short content
    if len(content_str) < 15:
        return True
        
    # Check for content that is mostly whitespace or special characters
    alphanumeric_count = len(re.sub(r'[^\w\s]', '', content_str))
    if alphanumeric_count < len(content_str) * 0.2:
        return True
        
    # Check for common low-quality patterns
    return any(pattern.search(content_str) for pattern in LOW_QUALITY_PATTERNS)


@dataclass
class MemoryEntry:
    """Represents a memory entry in the store"""
    id: str
    type: str  # 'conversation', 'context', 'pattern', 'change'
    content: Dict[str, Any]
    timestamp: str
    file_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)


class ChromaMemoryStore:
    """ChromaDB-based memory storage for agentic context and conversations"""
    
    COLLECTION_CONFIGS = {
        "memories": "General memory storage for conversations, context, and patterns",
        "code_patterns": "Code patterns and reusable snippets",
        "relationships": "Context relationships between memory items"
    }
    
    def __init__(self, context_manager, logger: Logger):
        self.logger = logger
        self.client = None
        self.project_root = None
        self.context_manager = context_manager
        self.collections = {}
        
    async def initialize(self, project_root: str = None):
        """Initialize ChromaDB memory store for a project"""
        if project_root is None:
            project_root = "."
        self.project_root = Path(project_root)
        
        # Create .k2edit directory if it doesn't exist
        chroma_path = self.project_root / ".k2edit" / "chroma_db"
        chroma_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client in a background thread to avoid blocking
        self.client = await asyncio.to_thread(
            chromadb.PersistentClient, 
            path=str(chroma_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True
            )
        )
        
        # Initialize collections
        await self._init_collections()
        
        await self.logger.info(f"ChromaDB memory store initialized at {chroma_path}")
        
    async def _init_collections(self):
        """Initialize ChromaDB collections for different data types"""
        for name, description in self.COLLECTION_CONFIGS.items():
            try:
                collection = await asyncio.to_thread(
                    self.client.get_or_create_collection,
                    name=name,
                    metadata={"description": description}
                )
                self.collections[name] = collection
                await self.logger.debug(f"Initialized collection: {name}")
            except Exception as e:
                await self.logger.error(f"Failed to initialize collection {name}: {e}")
                raise
                
    def _create_memory_entry(self, entry_type: str, content: Dict[str, Any], 
                           file_path: Optional[str] = None, tags: Optional[List[str]] = None,
                           prefix: Optional[str] = None) -> MemoryEntry:
        """Create a memory entry with common fields."""
        return MemoryEntry(
            id=self._generate_id(prefix),
            type=entry_type,
            content=content,
            timestamp=datetime.now().isoformat(),
            file_path=file_path,
            tags=tags or []
        )
    
    async def store_conversation(self, conversation: Dict[str, Any]):
        """Store a conversation entry"""
        entry = self._create_memory_entry("conversation", conversation)
        await self._store_memory(entry)
        
    async def store_context(self, file_path: str, context: Dict[str, Any]):
        """Store code context for a file"""
        tags = ["code", "context", Path(file_path).suffix]
        entry = self._create_memory_entry("context", context, file_path, tags, f"context_{file_path}")
        await self._store_memory(entry)
        
    async def store_change(self, change: Dict[str, Any]):
        """Store a code change"""
        entry = self._create_memory_entry("change", change, change.get("file_path"))
        await self._store_memory(entry)
        
    async def store_pattern(self, pattern_type: str, content: str, context: Dict[str, Any]):
        """Store a code pattern for future reference"""
        pattern_hash = self._hash_content(content)
        entry_id = self._generate_id()
        
        # Check if pattern already exists
        existing = await self._find_existing_pattern(pattern_hash)
        
        if existing:
            # Update usage count in metadata
            await self._update_pattern_usage(existing["id"], pattern_hash)
        else:
            # Store new pattern
            pattern_data = {
                "pattern_hash": pattern_hash,
                "pattern_type": pattern_type,
                "content": content,
                "context": json.dumps(context) if context else None,
                "usage_count": 1,
                "last_used": datetime.now().isoformat()
            }
            
            # Generate embedding for the pattern content
            embedding = await self._get_embedding(content)
            
            self.collections["code_patterns"].upsert(
                ids=[entry_id],
                documents=[content],
                metadatas=[pattern_data],
                embeddings=[embedding]
            )
            
    async def _find_existing_pattern(self, pattern_hash: str) -> Optional[Dict[str, Any]]:
        """Find existing pattern by hash"""
        try:
            results = self.collections["code_patterns"].get(
                where={"pattern_hash": pattern_hash},
                limit=1
            )
            
            if results["ids"]:
                return {
                    "id": results["ids"][0],
                    "metadata": results["metadatas"][0]
                }
        except Exception as e:
            await self.logger.error(f"Error finding existing pattern: {e}")
            
        return None
        
    async def _update_pattern_usage(self, pattern_id: str, pattern_hash: str):
        """Update pattern usage count"""
        try:
            # Get current metadata
            results = self.collections["code_patterns"].get(
                ids=[pattern_id],
                include=["metadatas", "documents"]
            )
            
            if results["ids"]:
                metadata = results["metadatas"][0]
                document = results["documents"][0]
                
                # Update usage count and last used
                metadata["usage_count"] = metadata.get("usage_count", 0) + 1
                metadata["last_used"] = datetime.now().isoformat()
                
                # Generate new embedding
                embedding = await self._get_embedding(document)
                
                # Update the record
                self.collections["code_patterns"].upsert(
                    ids=[pattern_id],
                    documents=[document],
                    metadatas=[metadata],
                    embeddings=[embedding]
                )
                
        except Exception as e:
            await self.logger.error(f"Error updating pattern usage: {e}")
            
    async def search_relevant_context(self, query: str, limit: int = 10, max_distance: float = 1.5) -> List[Dict[str, Any]]:
        """Search for relevant context based on query using semantic search with distance filtering"""
        # Generate embedding for the query
        query_embedding = await self._get_embedding(query)
        if not any(query_embedding):  # Check if it's all zeros
            await self.logger.error("Failed to generate valid embedding for query")
            return []
        
        # Search in memories collection with higher limit for filtering
        try:
            results = self.collections["memories"].query(
                query_embeddings=[query_embedding],
                n_results=limit * 2,  # Get more results to allow filtering
                where={"type": {"$in": ["conversation", "context", "pattern", "change"]}}
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB query failed: {e}")
            return []
        
        # Early return if no distances available - distance filtering is essential
        if "distances" not in results or not results["distances"] or not results["distances"][0]:
            await self.logger.warning("No distances returned from ChromaDB query - cannot perform distance filtering")
            return []
        
        # Process and filter results
        try:
            relevant = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                
                # Apply distance-based filtering
                if distance <= max_distance:
                    try:
                        content = json.loads(results["documents"][0][i])
                    except (json.JSONDecodeError, TypeError) as e:
                        await self.logger.warning(f"Failed to parse document content for {doc_id}: {e}")
                        continue
                    
                    # Additional quality filtering
                    if not self._is_low_quality_content(content):
                        # Content size filtering - limit to 1000 characters
                        content_size = len(json.dumps(content))
                        if content_size <= 1000:
                            relevant.append({
                                "id": doc_id,
                                "content": content,
                                "metadata": results["metadatas"][0][i],
                                "distance": distance,
                                "relevance_score": max(0, 1.0 - (distance / max_distance)),
                                "content_size": content_size
                            })
                        else:
                            await self.logger.debug(f"Filtered out large content item: {content_size} chars, distance: {distance}")
            
            # Sort by distance (closest first) and limit results
            relevant.sort(key=lambda x: x["distance"])
            return relevant[:limit]
            
        except Exception as e:
            await self.logger.error(f"Error processing search results: {e}")
            return []
            
    async def find_similar_code(self, code: str, limit: int = 5, max_distance: float = 1.2) -> List[Dict[str, Any]]:
        """Find similar code patterns with distance filtering"""
        # Generate embedding for the code
        code_embedding = await self._get_embedding(code)
        if not any(code_embedding):  # Check if it's all zeros
            await self.logger.error("Failed to generate valid embedding for code")
            return []
        
        # Search in code_patterns collection with more results for filtering
        try:
            results = self.collections["code_patterns"].query(
                query_embeddings=[code_embedding],
                n_results=limit * 2  # Get more results to allow filtering
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB code patterns query failed: {e}")
            return []
        
        # Early return if no distances available - distance filtering is essential
        if "distances" not in results or not results["distances"] or not results["distances"][0]:
            await self.logger.warning("No distances returned from ChromaDB query - cannot perform distance filtering")
            return []
        
        # Process and filter results
        try:
            similar = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                
                # Apply distance-based filtering
                if distance <= max_distance:
                    metadata = results["metadatas"][0][i]
                    context_data = metadata.get("context")
                    if context_data:
                        try:
                            context = json.loads(context_data)
                        except (json.JSONDecodeError, TypeError) as e:
                            await self.logger.warning(f"Failed to parse context data for {doc_id}: {e}")
                            context = {}
                    else:
                        context = {}
                        
                    similar.append({
                        "id": doc_id,
                        "content": results["documents"][0][i],
                        "type": metadata.get("pattern_type", "unknown"),
                        "usage_count": metadata.get("usage_count", 0),
                        "last_used": metadata.get("last_used"),
                        "context": context,
                        "distance": distance,
                        "relevance_score": max(0, 1.0 - (distance / max_distance))
                    })
            
            # Sort by distance (closest first) and limit results
            similar.sort(key=lambda x: x["distance"])
            return similar[:limit]
            
        except Exception as e:
            await self.logger.error(f"Error processing code search results: {e}")
            return []
            
    async def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        # Query ChromaDB for conversation memories
        try:
            results = self.collections["memories"].get(
                where={"type": "conversation"},
                limit=limit,
                include=["documents", "metadatas"]
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB query failed for recent conversations: {e}")
            return []
        
        # Process conversation results
        try:
            conversations = []
            for i, doc_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]
                try:
                    content = json.loads(results["documents"][i])
                except (json.JSONDecodeError, TypeError) as e:
                    await self.logger.warning(f"Failed to parse conversation content for {doc_id}: {e}")
                    continue
                    
                conversations.append({
                    "id": doc_id,
                    "content": content,
                    "timestamp": metadata.get("timestamp")
                })
                
            # Sort by timestamp (most recent first)
            conversations.sort(key=lambda x: x["timestamp"], reverse=True)
            return conversations[:limit]
            
        except Exception as e:
            await self.logger.error(f"Error processing conversation results: {e}")
            return []
            
    async def get_file_context(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get stored context for a specific file"""
        # Query ChromaDB for file context
        try:
            results = self.collections["memories"].get(
                where={
                    "$and": [
                        {"type": "context"},
                        {"file_path": file_path}
                    ]
                },
                limit=1,
                include=["documents", "metadatas"]
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB query failed for file context {file_path}: {e}")
            return None
        
        # Process file context results
        if results["ids"]:
            try:
                metadata = results["metadatas"][0]
                context_data = json.loads(results["documents"][0])
                return {
                    "context": context_data,
                    "timestamp": metadata.get("timestamp")
                }
            except (json.JSONDecodeError, TypeError, Exception) as e:
                error_type = type(e).__name__
                if isinstance(e, (json.JSONDecodeError, TypeError)):
                    await self.logger.error(f"Failed to parse file context data for {file_path}: {e}")
                else:
                    await self.logger.error(f"Error processing file context for {file_path}: {e}")
                return None
                
        return None
        
    async def _store_memory(self, memory_entry: MemoryEntry):
        """Store a memory entry in ChromaDB"""
        try:
            # Generate embedding for the content
            content_str = json.dumps(memory_entry.content)
            embedding = await self._get_embedding(content_str)
            if not any(embedding):  # Check if it's all zeros
                await self.logger.error("Failed to generate embedding for memory content - cannot store memory")
                raise RuntimeError("Failed to generate embedding for memory storage")
            
            # Prepare metadata
            metadata = {
                "type": memory_entry.type,
                "timestamp": memory_entry.timestamp,
                "file_path": memory_entry.file_path,
                "tags": json.dumps(memory_entry.tags) if memory_entry.tags else None,
                "semantic_score": 1.0,
                "access_count": 0,
                "last_accessed": None
            }
            
            # Store in ChromaDB
            self.collections["memories"].upsert(
                ids=[memory_entry.id],
                documents=[content_str],
                metadatas=[metadata],
                embeddings=[embedding]
            )
            
        except Exception as e:
            await self.logger.error(f"Error storing memory: {e}")
            raise
            
    async def _get_embedding(self, content: str) -> List[float]:
        """Generate embedding with fallback to zero vector."""
        if self.context_manager is None:
            return [0.0] * 384
        
        try:
            embedding = await self.context_manager._generate_embedding(content)
            return embedding if embedding is not None else [0.0] * 384
        except Exception as e:
            await self.logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * 384
    
    def _generate_id(self, prefix: str = None) -> str:
        """Generate a unique ID for memory entries"""
        prefix_str = f"{prefix}_" if prefix else ""
        return f"{prefix_str}{uuid.uuid4().hex[:12]}"
        
    def _hash_content(self, content: str) -> str:
        """Generate hash for content"""
        return hashlib.md5(content.encode()).hexdigest()

    def _is_low_quality_content(self, content: Any) -> bool:
        """Check if content is low quality and should be filtered out"""
        return _is_low_quality_content_static(content)
    
    async def semantic_search(self, query: str, limit: int = 5, max_distance: float = 1.5) -> List[Dict[str, Any]]:
        """Perform semantic search using ChromaDB's native vector search with distance filtering"""
        # Generate embedding for the query
        query_embedding = await self._get_embedding(query)
        if not any(query_embedding):  # Check if it's all zeros
            await self.logger.error("Failed to generate valid embedding for semantic search")
            return []
        
        # Search across all memories with higher limit for filtering
        try:
            results = self.collections["memories"].query(
                query_embeddings=[query_embedding],
                n_results=limit * 2,  # Get more results for filtering
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB semantic search query failed: {e}")
            return []
        
        # Process search results with multiprocessing optimization
        try:
            doc_ids = results["ids"][0]
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            
            # Use multiprocessing for large result sets (>30 results)
            if len(doc_ids) > 30:
                search_results = await self._process_search_results_multiprocess(
                    doc_ids, documents, metadatas, distances, max_distance
                )
            else:
                search_results = await self._process_search_results_sequential(
                    doc_ids, documents, metadatas, distances, max_distance
                )
            
            # Sort by distance (closest first) and limit results
            search_results.sort(key=lambda x: x["distance"])
            return search_results[:limit]
            
        except Exception as e:
            await self.logger.error(f"Error processing semantic search results: {e}")
            return []
    
    async def _process_search_results_sequential(self, doc_ids: List[str], documents: List[str],
                                               metadatas: List[Dict], distances: List[float],
                                               max_distance: float) -> List[Dict[str, Any]]:
        """Process search results sequentially for smaller result sets."""
        search_results = []
        
        for i, doc_id in enumerate(doc_ids):
            distance = distances[i]
            
            # Apply distance-based filtering
            if distance <= max_distance:
                try:
                    content = json.loads(documents[i])
                except (json.JSONDecodeError, TypeError) as e:
                    await self.logger.warning(f"Failed to parse search result content for {doc_id}: {e}")
                    continue
                
                # Apply quality filtering
                if not self._is_low_quality_content(content):
                    search_results.append({
                        "id": doc_id,
                        "content": content,
                        "metadata": metadatas[i],
                        "distance": distance,
                        "similarity": 1.0 - distance,  # Convert distance to similarity
                        "relevance_score": max(0, 1.0 - (distance / max_distance))
                    })
        
        return search_results
    
    async def _process_search_results_multiprocess(self, doc_ids: List[str], documents: List[str],
                                                  metadatas: List[Dict], distances: List[float],
                                                  max_distance: float) -> List[Dict[str, Any]]:
        """Process search results using multiprocessing for large result sets."""
        # Determine optimal number of processes
        num_processes = min(mp.cpu_count(), max(2, len(doc_ids) // 15))
        
        # Create chunks of results for each process
        chunk_size = max(1, len(doc_ids) // num_processes)
        result_chunks = []
        
        for i in range(0, len(doc_ids), chunk_size):
            chunk_data = list(zip(
                doc_ids[i:i + chunk_size],
                documents[i:i + chunk_size],
                metadatas[i:i + chunk_size],
                distances[i:i + chunk_size]
            ))
            result_chunks.append(chunk_data)
        
        # Create partial function with search parameters
        process_func = partial(_process_search_results_chunk, 
                              max_distance=max_distance, quality_filter=True)
        
        # Execute optimized processing using thread pool for CPU-bound operations
        thread_pool = get_thread_pool()
        chunk_results = []
        for chunk in result_chunks:
            result = await thread_pool.run_cpu_bound(process_func, chunk)
            chunk_results.append(result)
        
        # Flatten results from all chunks
        search_results = []
        for chunk_result in chunk_results:
            for result in chunk_result:
                # Add similarity score for compatibility
                result["similarity"] = 1.0 - result["distance"]
                search_results.append(result)
        
        return search_results
    
    async def update_memory_score(self, memory_id: str, score_change: float):
        """Update the semantic score of a memory based on usage"""
        # Get current record
        try:
            results = self.collections["memories"].get(
                ids=[memory_id],
                include=["documents", "metadatas"]
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB query failed for memory {memory_id}: {e}")
            return
        
        if not results["ids"]:
            await self.logger.warning(f"Memory {memory_id} not found for score update")
            return
        
        # Process memory record
        try:
            metadata = results["metadatas"][0]
            document = results["documents"][0]
            
            # Update metadata
            metadata["semantic_score"] = metadata.get("semantic_score", 1.0) + score_change
            metadata["access_count"] = metadata.get("access_count", 0) + 1
            metadata["last_accessed"] = datetime.now().isoformat()
        except Exception as e:
            await self.logger.error(f"Error processing memory metadata for {memory_id}: {e}")
            return
        
        # Generate new embedding
        embedding = await self._get_embedding(document)
        if not any(embedding):  # Check if it's all zeros
            await self.logger.error(f"Failed to generate embedding for memory {memory_id} - cannot update")
            return
        
        # Update the record
        try:
            self.collections["memories"].upsert(
                ids=[memory_id],
                documents=[document],
                metadatas=[metadata],
                embeddings=[embedding]
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB upsert failed for memory {memory_id}: {e}")
    
    async def add_context_relationship(self, source_id: str, target_id: str, relationship_type: str, weight: float = 1.0, metadata: Dict[str, Any] = None):
        """Add a relationship between two context items"""
        # Prepare relationship data
        try:
            relationship_id = self._generate_id()
            
            relationship_data = {
                "source_id": source_id,
                "target_id": target_id,
                "relationship_type": relationship_type,
                "weight": weight,
                "timestamp": datetime.now().isoformat(),
                "metadata": json.dumps(metadata) if metadata else None
            }
            
            # Create a document for the relationship
            relationship_doc = f"{relationship_type}: {source_id} -> {target_id}"
        except Exception as e:
            await self.logger.error(f"Error preparing relationship data: {e}")
            return
        
        # Generate embedding for the relationship
        embedding = await self._get_embedding(relationship_doc)
        if not any(embedding):  # Check if it's all zeros
            await self.logger.error("Failed to generate embedding for relationship - cannot store")
            return
        
        # Store the relationship
        try:
            self.collections["relationships"].upsert(
                ids=[relationship_id],
                documents=[relationship_doc],
                metadatas=[relationship_data],
                embeddings=[embedding]
            )
        except Exception as e:
            await self.logger.error(f"ChromaDB upsert failed for relationship: {e}")
    
    async def get_related_context(self, memory_id: str, relationship_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get related context items based on relationships"""
        try:
            where_clause = {"source_id": memory_id}
            if relationship_type:
                where_clause["relationship_type"] = relationship_type
                
            results = self.collections["relationships"].get(
                where=where_clause,
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            related = []
            for i, rel_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]
                target_id = metadata["target_id"]
                
                # Get the target memory
                target_results = self.collections["memories"].get(
                    ids=[target_id],
                    include=["documents", "metadatas"]
                )
                
                if target_results["ids"]:
                    target_metadata = target_results["metadatas"][0]
                    related.append({
                        "id": target_id,
                        "content": json.loads(target_results["documents"][0]),
                        "timestamp": target_metadata.get("timestamp"),
                        "type": target_metadata.get("type"),
                        "relationship_type": metadata["relationship_type"],
                        "weight": metadata["weight"]
                    })
            
            # Sort by weight (highest first)
            related.sort(key=lambda x: x["weight"], reverse=True)
            return related
            
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error getting related context: {e}")
            return []
    
    async def cleanup_old_memories(self, days: int = 30):
        """Clean up memories older than specified days with semantic scoring consideration"""
        try:
            cutoff_timestamp = datetime.now().timestamp() - (days * 24 * 60 * 60)
            cutoff_date = datetime.fromtimestamp(cutoff_timestamp).isoformat()
            
            # Get old memories with low scores
            results = self.collections["memories"].get(
                where={
                    "$and": [
                        {"timestamp": {"$lt": cutoff_date}},
                        {"semantic_score": {"$lt": 0.5}}
                    ]
                },
                include=["metadatas"]
            )
            
            if results["ids"]:
                # Delete old, low-scoring memories
                self.collections["memories"].delete(ids=results["ids"])
                if self.logger:
                    await self.logger.info(f"Cleaned up {len(results['ids'])} old memories")
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error cleaning up old memories: {e}")
            
    async def export_memories(self, output_path: str):
        """Export all memories to JSON file"""
        try:
            export_data = {
                "memories": [],
                "code_patterns": [],
                "relationships": []
            }
            
            # Export memories
            memories = self.collections["memories"].get(include=["documents", "metadatas"])
            for i, memory_id in enumerate(memories["ids"]):
                export_data["memories"].append({
                    "id": memory_id,
                    "content": json.loads(memories["documents"][i]),
                    "metadata": memories["metadatas"][i]
                })
            
            # Export code patterns
            patterns = self.collections["code_patterns"].get(include=["documents", "metadatas"])
            for i, pattern_id in enumerate(patterns["ids"]):
                export_data["code_patterns"].append({
                    "id": pattern_id,
                    "content": patterns["documents"][i],
                    "metadata": patterns["metadatas"][i]
                })
            
            # Export relationships
            relationships = self.collections["relationships"].get(include=["documents", "metadatas"])
            for i, rel_id in enumerate(relationships["ids"]):
                export_data["relationships"].append({
                    "id": rel_id,
                    "content": relationships["documents"][i],
                    "metadata": relationships["metadatas"][i]
                })
            
            async with aiofiles.open(output_path, 'w') as f:
                await f.write(json.dumps(export_data, indent=2, default=str))
                
            await self.logger.info(f"Exported memories to {output_path}")
        except Exception as e:
            await self.logger.error(f"Error exporting memories: {e}")