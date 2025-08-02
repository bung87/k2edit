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
        
    async def initialize(self, project_root: str):
        """Initialize memory store for a project"""
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
                    embedding TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_type ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);
                CREATE INDEX IF NOT EXISTS idx_file_path ON memories(file_path);
                
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
        
    async def cleanup_old_memories(self, days: int = 30):
        """Clean up memories older than specified days"""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        async with self._get_connection() as conn:
            await conn.execute("""
                DELETE FROM memories
                WHERE timestamp < datetime(?, 'unixepoch')
            """, (cutoff_date,))
            await conn.commit()
            
    async def export_memories(self, output_path: str):
        """Export all memories to JSON file"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM memories ORDER BY timestamp")
            results = await cursor.fetchall()
            
            memories = []
            for row in results:
                memories.append({
                    "id": row[0],
                    "type": row[1],
                    "content": json.loads(row[2]),
                    "timestamp": row[3],
                    "file_path": row[4],
                    "tags": json.loads(row[5]) if row[5] else [],
                    "embedding": json.loads(row[6]) if row[6] else None
                })
                
            with open(output_path, 'w') as f:
                json.dump(memories, f, indent=2, default=str)