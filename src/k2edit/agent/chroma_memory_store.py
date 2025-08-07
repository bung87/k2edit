"""ChromaDB-based Memory Store for K2Edit Agentic System
Handles persistent storage of conversations, code context, and learned patterns using ChromaDB
for native vector embedding support.
"""

import json
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import hashlib
import numpy as np
import chromadb
from chromadb.config import Settings
from aiologger import Logger


@dataclass
class MemoryEntry:
    """Represents a memory entry in the store"""
    id: str
    type: str  # 'conversation', 'context', 'pattern', 'change'
    content: Dict[str, Any]
    timestamp: str
    file_path: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class ChromaMemoryStore:
    """ChromaDB-based memory storage for agentic context and conversations"""
    
    def __init__(self, context_manager, logger: Logger = None):
        self.logger = logger or Logger.with_default_handlers(name="k2edit")
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
        
        # Initialize collections in background
        asyncio.create_task(self._init_collections())
        
        if self.logger:
            await self.logger.info(f"ChromaDB memory store initialized at {chroma_path}")
        
    async def _init_collections(self):
        """Initialize ChromaDB collections for different data types"""
        collection_configs = {
            "memories": "General memory storage for conversations, context, and patterns",
            "code_patterns": "Code patterns and reusable snippets",
            "relationships": "Context relationships between memory items"
        }
        
        for name, description in collection_configs.items():
            try:
                # Get or create collection
                collection = await asyncio.to_thread(
                    self.client.get_or_create_collection,
                    name=name,
                    metadata={"description": description}
                )
                self.collections[name] = collection
                if self.logger:
                    await self.logger.debug(f"Initialized collection: {name}")
            except Exception as e:
                if self.logger:
                    await self.logger.error(f"Failed to initialize collection {name}: {e}")
                raise
                
    async def store_conversation(self, conversation: Dict[str, Any]):
        """Store a conversation entry"""
        entry_id = self._generate_id()
        
        memory_entry = MemoryEntry(
            id=entry_id,
            type="conversation",
            content=conversation,
            timestamp=datetime.now().isoformat()
        )
        
        await self._store_memory(memory_entry)
        
    async def store_context(self, file_path: str, context: Dict[str, Any]):
        """Store code context for a file"""
        entry_id = self._generate_id(f"context_{file_path}")
        
        memory_entry = MemoryEntry(
            id=entry_id,
            type="context",
            content=context,
            timestamp=datetime.now().isoformat(),
            file_path=file_path,
            tags=["code", "context", Path(file_path).suffix]
        )
        
        await self._store_memory(memory_entry)
        
    async def store_change(self, change: Dict[str, Any]):
        """Store a code change"""
        entry_id = self._generate_id()
        
        memory_entry = MemoryEntry(
            id=entry_id,
            type="change",
            content=change,
            timestamp=datetime.now().isoformat(),
            file_path=change.get("file_path")
        )
        
        await self._store_memory(memory_entry)
        
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
            if self.context_manager is None:
                embedding = [0.0] * 384  # Default zero vector
            else:
                embedding = await self.context_manager._generate_embedding(content)
                if embedding is None:
                    embedding = [0.0] * 384  # Fallback zero vector
            
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
            if self.logger:
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
                if self.context_manager is None:
                    embedding = [0.0] * 384  # Default zero vector
                else:
                    embedding = await self.context_manager._generate_embedding(document)
                    if embedding is None:
                        embedding = [0.0] * 384  # Fallback zero vector
                
                # Update the record
                self.collections["code_patterns"].upsert(
                    ids=[pattern_id],
                    documents=[document],
                    metadatas=[metadata],
                    embeddings=[embedding]
                )
                
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error updating pattern usage: {e}")
            
    async def search_relevant_context(self, query: str, limit: int = 10, max_distance: float = 1.5) -> List[Dict[str, Any]]:
        """Search for relevant context based on query using semantic search with distance filtering"""
        try:
            # Generate embedding for the query
            if self.context_manager is None:
                query_embedding = [0.0] * 384  # Default zero vector
            else:
                query_embedding = await self.context_manager._generate_embedding(query)
                if query_embedding is None:
                    query_embedding = [0.0] * 384  # Fallback zero vector
            
            # Search in memories collection with higher limit for filtering
            results = self.collections["memories"].query(
                query_embeddings=[query_embedding],
                n_results=limit * 2,  # Get more results to allow filtering
                where={"type": {"$in": ["conversation", "context", "pattern"]}}
            )
            
            relevant = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if "distances" in results else 0.0
                
                # Apply distance-based filtering
                if distance <= max_distance:
                    content = json.loads(results["documents"][0][i])
                    
                    # Additional quality filtering
                    if not self._is_low_quality_content(content):
                        relevant.append({
                            "id": doc_id,
                            "content": content,
                            "metadata": results["metadatas"][0][i],
                            "distance": distance,
                            "relevance_score": max(0, 1.0 - (distance / max_distance))
                        })
            
            # Sort by distance (closest first) and limit results
            relevant.sort(key=lambda x: x["distance"])
            return relevant[:limit]
            
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error searching relevant context: {e}")
            return []
            
    async def find_similar_code(self, code: str, limit: int = 5, max_distance: float = 1.2) -> List[Dict[str, Any]]:
        """Find similar code patterns with distance filtering"""
        try:
            # Generate embedding for the code
            if self.context_manager is None:
                code_embedding = [0.0] * 384  # Default zero vector
            else:
                code_embedding = await self.context_manager._generate_embedding(code)
                if code_embedding is None:
                    code_embedding = [0.0] * 384  # Fallback zero vector
            
            # Search in code_patterns collection with more results for filtering
            results = self.collections["code_patterns"].query(
                query_embeddings=[code_embedding],
                n_results=limit * 2  # Get more results to allow filtering
            )
            
            similar = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if "distances" in results else 0.0
                
                # Apply distance-based filtering
                if distance <= max_distance:
                    metadata = results["metadatas"][0][i]
                    context_data = metadata.get("context")
                    if context_data:
                        try:
                            context = json.loads(context_data)
                        except (json.JSONDecodeError, TypeError):
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
            if self.logger:
                await self.logger.error(f"Error finding similar code: {e}")
            return []
            
    async def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        try:
            results = self.collections["memories"].get(
                where={"type": "conversation"},
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            conversations = []
            for i, doc_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]
                conversations.append({
                    "id": doc_id,
                    "content": json.loads(results["documents"][i]),
                    "timestamp": metadata.get("timestamp")
                })
                
            # Sort by timestamp (most recent first)
            conversations.sort(key=lambda x: x["timestamp"], reverse=True)
            return conversations[:limit]
            
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error getting recent conversations: {e}")
            return []
            
    async def get_file_context(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get stored context for a specific file"""
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
            
            if results["ids"]:
                metadata = results["metadatas"][0]
                return {
                    "context": json.loads(results["documents"][0]),
                    "timestamp": metadata.get("timestamp")
                }
                
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error getting file context: {e}")
            
        return None
        
    async def _store_memory(self, memory_entry: MemoryEntry):
        """Store a memory entry in ChromaDB"""
        try:
            # Generate embedding for the content
            content_str = json.dumps(memory_entry.content)
            if self.context_manager is None:
                embedding = [0.0] * 384  # Default zero vector
            else:
                embedding = await self.context_manager._generate_embedding(content_str)
                if embedding is None:
                    embedding = [0.0] * 384  # Fallback zero vector
            
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
            if self.logger:
                await self.logger.error(f"Error storing memory: {e}")
            raise
            
    def _generate_id(self, prefix: str = None) -> str:
        """Generate a unique ID for memory entries"""
        import uuid
        prefix_str = f"{prefix}_" if prefix else ""
        return f"{prefix_str}{uuid.uuid4().hex[:12]}"
        
    def _hash_content(self, content: str) -> str:
        """Generate hash for content"""
        return hashlib.md5(content.encode()).hexdigest()

    def _is_low_quality_content(self, content: Any) -> bool:
        """Check if content is low quality and should be filtered out"""
        if not content:
            return True
            
        import re
        
        # Extract actual code content from the memory entry
        content_str = ""
        if isinstance(content, dict):
            # Handle memory entry format
            if 'code' in content:
                content_str = content['code']
            elif 'content' in content and isinstance(content['content'], dict) and 'code' in content['content']:
                content_str = content['content']['code']
            else:
                content_str = str(content)
        else:
            content_str = str(content)
            
        content_str = content_str.strip()
        
        # Check for very short content
        if len(content_str) < 15:
            return True
            
        # Check for content that is mostly whitespace or special characters
        alphanumeric_count = len(re.sub(r'[^\w\s]', '', content_str))
        if alphanumeric_count < len(content_str) * 0.2:
            return True
            
        # Check for common low-quality patterns
        low_quality_patterns = [
            r'console\.log',
            r'print\s*\(',
            r'\b(TODO|FIXME|HACK|XXX)\b',
            r'^\s*import\s+\w+\s*$',
            r'^\s*from\s+\w+\s+import\s+\w+\s*$',
            r'^\s*(var|let|const)\s+\w+\s*=\s*\w+\s*$',
            r'\btemp\d*\b',
            r'\btmp\d*\b',
        ]
        
        for pattern in low_quality_patterns:
            if re.search(pattern, content_str, re.IGNORECASE):
                return True
                
        return False
    
    async def semantic_search(self, query: str, limit: int = 5, max_distance: float = 1.5) -> List[Dict[str, Any]]:
        """Perform semantic search using ChromaDB's native vector search with distance filtering"""
        try:
            # Generate embedding for the query
            if self.context_manager is None:
                query_embedding = [0.0] * 384  # Default zero vector
            else:
                query_embedding = await self.context_manager._generate_embedding(query)
                if query_embedding is None:
                    query_embedding = [0.0] * 384  # Fallback zero vector
            
            # Search across all memories with higher limit for filtering
            results = self.collections["memories"].query(
                query_embeddings=[query_embedding],
                n_results=limit * 2,  # Get more results for filtering
                include=["documents", "metadatas", "distances"]
            )
            
            search_results = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                
                # Apply distance-based filtering
                if distance <= max_distance:
                    content = json.loads(results["documents"][0][i])
                    
                    # Apply quality filtering
                    if not self._is_low_quality_content(content):
                        search_results.append({
                            "id": doc_id,
                            "content": content,
                            "metadata": results["metadatas"][0][i],
                            "distance": distance,
                            "similarity": 1.0 - distance,  # Convert distance to similarity
                            "relevance_score": max(0, 1.0 - (distance / max_distance))
                        })
            
            # Sort by distance (closest first) and limit results
            search_results.sort(key=lambda x: x["distance"])
            return search_results[:limit]
            
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error in semantic search: {e}")
            return []
    
    async def update_memory_score(self, memory_id: str, score_change: float):
        """Update the semantic score of a memory based on usage"""
        try:
            # Get current record
            results = self.collections["memories"].get(
                ids=[memory_id],
                include=["documents", "metadatas"]
            )
            
            if results["ids"]:
                metadata = results["metadatas"][0]
                document = results["documents"][0]
                
                # Update metadata
                metadata["semantic_score"] = metadata.get("semantic_score", 1.0) + score_change
                metadata["access_count"] = metadata.get("access_count", 0) + 1
                metadata["last_accessed"] = datetime.now().isoformat()
                
                # Generate new embedding
                if self.context_manager is None:
                    embedding = [0.0] * 384  # Default zero vector
                else:
                    embedding = await self.context_manager._generate_embedding(document)
                    if embedding is None:
                        embedding = [0.0] * 384  # Fallback zero vector
                
                # Update the record
                self.collections["memories"].upsert(
                    ids=[memory_id],
                    documents=[document],
                    metadatas=[metadata],
                    embeddings=[embedding]
                )
                
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error updating memory score: {e}")
    
    async def add_context_relationship(self, source_id: str, target_id: str, relationship_type: str, weight: float = 1.0, metadata: Dict[str, Any] = None):
        """Add a relationship between two context items"""
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
            
            # Generate embedding for the relationship
            if self.context_manager is None:
                embedding = [0.0] * 384  # Default zero vector
            else:
                embedding = await self.context_manager._generate_embedding(relationship_doc)
                if embedding is None:
                    embedding = [0.0] * 384  # Fallback zero vector
            
            self.collections["relationships"].upsert(
                ids=[relationship_id],
                documents=[relationship_doc],
                metadatas=[relationship_data],
                embeddings=[embedding]
            )
            
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error adding context relationship: {e}")
    
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
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
                
            if self.logger:
                await self.logger.info(f"Exported memories to {output_path}")
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error exporting memories: {e}")