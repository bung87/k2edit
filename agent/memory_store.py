"""
Memory Store for K2Edit Agentic System
Handles persistent storage of conversations, code context, and learned patterns
"""

import json
import logging
import aiosqlite as sqlite3
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import hashlib
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import re


@dataclass
class MemoryEntry:
    """Represents a memory entry in the store"""
    id: str
    type: str  # 'conversation', 'context', 'pattern', 'change'
    content: Dict[str, Any]
    timestamp: str
    file_path: Optional[str] = None
    tags: List[str] = None
    embedding: Optional[List[float]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class MemoryStore:
    """Persistent memory storage for agentic context and conversations"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self.db_path = None
        self.project_root = None
        
    async def initialize(self, project_root: str = None):
        """Initialize memory store for a project"""
        if project_root is None:
            project_root = "."
        self.project_root = Path(project_root)
        self.db_path = self.project_root / ".k2edit" / "memory.db"
        
        # Create .k2edit directory if it doesn't exist
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Initialize database
        await self._init_database()
        
        self.logger.info(f"Memory store initialized at {self.db_path}")
        
    async def _init_database(self):
        """Initialize the SQLite database with required tables"""
        async with sqlite3.connect(self.db_path) as conn:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    file_path TEXT,
                    tags TEXT,
                    embedding TEXT,
                    semantic_score REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_type ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);
                CREATE INDEX IF NOT EXISTS idx_file_path ON memories(file_path);
                CREATE INDEX IF NOT EXISTS idx_semantic_score ON memories(semantic_score);
                
                CREATE TABLE IF NOT EXISTS code_patterns (
                    id TEXT PRIMARY KEY,
                    pattern_hash TEXT UNIQUE,
                    pattern_type TEXT,
                    content TEXT,
                    usage_count INTEGER DEFAULT 1,
                    last_used TEXT,
                    context TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_pattern_type ON code_patterns(pattern_type);
                CREATE INDEX IF NOT EXISTS idx_pattern_hash ON code_patterns(pattern_hash);
            """)
            await conn.commit()
            

        
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
        
        async with sqlite3.connect(self.db_path) as conn:
            # Check if pattern already exists
            cursor = await conn.execute(
                "SELECT usage_count FROM code_patterns WHERE pattern_hash = ?",
                (pattern_hash,)
            )
            result = await cursor.fetchone()
            
            if result:
                # Update usage count
                await conn.execute(
                    "UPDATE code_patterns SET usage_count = usage_count + 1, last_used = ? WHERE pattern_hash = ?",
                    (datetime.now().isoformat(), pattern_hash)
                )
            else:
                # Insert new pattern
                entry_id = self._generate_id()
                await conn.execute(
                    "INSERT INTO code_patterns (id, pattern_hash, pattern_type, content, last_used, context) VALUES (?, ?, ?, ?, ?, ?)",
                    (entry_id, pattern_hash, pattern_type, content, datetime.now().isoformat(), json.dumps(context))
                )
                
            await conn.commit()
            
    async def search_relevant_context(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for relevant context based on query"""
        # Simple keyword-based search for now
        keywords = query.lower().split()
        
        async with sqlite3.connect(self.db_path) as conn:
            # Search in conversations and context
            cursor = await conn.execute("""
                SELECT content, timestamp, type, file_path, tags
                FROM memories
                WHERE type IN ('conversation', 'context', 'pattern')
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = await cursor.fetchall()
            
            # Filter by keywords
            relevant = []
            for row in results:
                content_str = json.dumps(row[0]).lower()
                if any(keyword in content_str for keyword in keywords):
                    relevant.append({
                        "content": json.loads(row[0]),
                        "timestamp": row[1],
                        "type": row[2],
                        "file_path": row[3],
                        "tags": row[4]
                    })
                    
            return relevant[:limit]
            
    async def find_similar_code(self, code: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar code patterns"""
        if not code:
            return []
            
        # Simple similarity based on content hash
        code_hash = self._hash_content(code)
        
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT content, pattern_type, usage_count, last_used, context
                FROM code_patterns
                WHERE pattern_hash LIKE ?
                ORDER BY usage_count DESC, last_used DESC
                LIMIT ?
            """, (f"%{code_hash[:8]}%", limit))
            
            results = await cursor.fetchall()
            
            return [{
                "content": row[0],
                "type": row[1],
                "usage_count": row[2],
                "last_used": row[3],
                "context": json.loads(row[4]) if row[4] else {}
            } for row in results]
            
    async def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT content, timestamp
                FROM memories
                WHERE type = 'conversation'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = await cursor.fetchall()
            
            return [{
                "content": json.loads(row[0]),
                "timestamp": row[1]
            } for row in results]
            
    async def get_file_context(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get stored context for a specific file"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT content, timestamp
                FROM memories
                WHERE type = 'context' AND file_path = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (file_path,))
            
            result = await cursor.fetchone()
            
            if result:
                return {
                    "context": json.loads(result[0]),
                    "timestamp": result[1]
                }
                
        return None
        
    async def _store_memory(self, memory_entry: MemoryEntry):
        """Store a memory entry in the database"""
        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO memories (id, type, content, timestamp, file_path, tags, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_entry.id,
                memory_entry.type,
                json.dumps(memory_entry.content),
                memory_entry.timestamp,
                memory_entry.file_path,
                json.dumps(memory_entry.tags) if memory_entry.tags else None,
                json.dumps(memory_entry.embedding) if memory_entry.embedding else None
            ))
            await conn.commit()
            
    def _generate_id(self, prefix: str = None) -> str:
        """Generate a unique ID for memory entries"""
        import uuid
        prefix_str = f"{prefix}_" if prefix else ""
        return f"{prefix_str}{uuid.uuid4().hex[:12]}"
        
    def _get_connection(self):
        """Get database connection with async support"""
        return sqlite3.connect(self.db_path)

    def _hash_content(self, content: str) -> str:
        """Generate hash for content"""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _generate_embedding(self, content: str) -> List[float]:
        """Generate semantic embedding for content using simple TF-IDF approach"""
        # Simple word-based embedding for now
        # In production, use sentence-transformers or similar
        words = re.findall(r'\b\w+\b', content.lower())
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Create a simple 100-dimensional embedding
        embedding = [0.0] * 100
        for i, (word, freq) in enumerate(word_freq.items()):
            if i < 100:
                # Use word hash to create consistent but varied values
                embedding[i] = float(freq) * (hash(word) % 1000) / 1000.0
        
        return embedding
    
    async def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Perform semantic search using embeddings"""
        query_embedding = self._generate_embedding(query)
        
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, content, embedding, timestamp, type, file_path, tags, semantic_score
                FROM memories
                WHERE embedding IS NOT NULL
                ORDER BY timestamp DESC
            """)
            
            results = await cursor.fetchall()
            
            semantic_matches = []
            for row in results:
                try:
                    stored_embedding = json.loads(row[2])
                    similarity = self._cosine_similarity(query_embedding, stored_embedding)
                    
                    if similarity >= threshold:
                        semantic_matches.append({
                            "id": row[0],
                            "content": json.loads(row[1]),
                            "timestamp": row[3],
                            "type": row[4],
                            "file_path": row[5],
                            "tags": json.loads(row[6]) if row[6] else [],
                            "similarity": similarity,
                            "semantic_score": row[7] if len(row) > 7 else 1.0
                        })
                except (json.JSONDecodeError, IndexError):
                    continue
            
            # Sort by similarity and return top results
            semantic_matches.sort(key=lambda x: x["similarity"], reverse=True)
            return semantic_matches[:limit]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def update_memory_score(self, memory_id: str, score_change: float):
        """Update the semantic score of a memory based on usage"""
        async with self._get_connection() as conn:
            await conn.execute("""
                UPDATE memories 
                SET semantic_score = semantic_score + ?, access_count = access_count + 1, last_accessed = ?
                WHERE id = ?
            """, (score_change, datetime.now().isoformat(), memory_id))
            await conn.commit()
    
    async def add_context_relationship(self, source_id: str, target_id: str, relationship_type: str, weight: float = 1.0, metadata: Dict[str, Any] = None):
        """Add a relationship between two context items"""
        relationship_id = self._generate_id()
        
        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO context_relationships (id, source_id, target_id, relationship_type, weight, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                relationship_id,
                source_id,
                target_id,
                relationship_type,
                weight,
                datetime.now().isoformat(),
                json.dumps(metadata) if metadata else None
            ))
            await conn.commit()
    
    async def get_related_context(self, memory_id: str, relationship_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get related context items based on relationships"""
        async with self._get_connection() as conn:
            if relationship_type:
                cursor = await conn.execute("""
                    SELECT cr.target_id, m.content, m.timestamp, m.type, cr.relationship_type, cr.weight
                    FROM context_relationships cr
                    JOIN memories m ON cr.target_id = m.id
                    WHERE cr.source_id = ? AND cr.relationship_type = ?
                    ORDER BY cr.weight DESC
                    LIMIT ?
                """, (memory_id, relationship_type, limit))
            else:
                cursor = await conn.execute("""
                    SELECT cr.target_id, m.content, m.timestamp, m.type, cr.relationship_type, cr.weight
                    FROM context_relationships cr
                    JOIN memories m ON cr.target_id = m.id
                    WHERE cr.source_id = ?
                    ORDER BY cr.weight DESC
                    LIMIT ?
                """, (memory_id, limit))
            
            results = await cursor.fetchall()
            
            return [{
                "id": row[0],
                "content": json.loads(row[1]),
                "timestamp": row[2],
                "type": row[3],
                "relationship_type": row[4],
                "weight": row[5]
            } for row in results]
    
    async def cleanup_old_memories(self, days: int = 30):
        """Clean up memories older than specified days with semantic scoring consideration"""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        async with self._get_connection() as conn:
            # Keep high-scoring memories even if old
            await conn.execute("""
                DELETE FROM memories
                WHERE timestamp < datetime(?, 'unixepoch')
                AND semantic_score < 0.5
            """, (cutoff_date,))
            await conn.commit()
            
    async def export_memories(self, output_path: str):
        """Export all memories to JSON file including relationships"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM memories ORDER BY timestamp")
            memories = await cursor.fetchall()
            
            relationships_cursor = await conn.execute("SELECT * FROM context_relationships ORDER BY timestamp")
            relationships = await relationships_cursor.fetchall()
            
            export_data = {
                "memories": [{
                    "id": row[0],
                    "type": row[1],
                    "content": json.loads(row[2]),
                    "timestamp": row[3],
                    "file_path": row[4],
                    "tags": json.loads(row[5]) if row[5] else [],
                    "embedding": json.loads(row[6]) if row[6] else None,
                    "semantic_score": row[7],
                    "access_count": row[8],
                    "last_accessed": row[9]
                } for row in memories],
                "relationships": [{
                    "id": row[0],
                    "source_id": row[1],
                    "target_id": row[2],
                    "relationship_type": row[3],
                    "weight": row[4],
                    "timestamp": row[5],
                    "metadata": json.loads(row[6]) if row[6] else None
                } for row in relationships]
            }
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)