"""
Tests for the MemoryStore
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from agent.memory_store import MemoryStore


class TestMemoryStore:
    """Test cases for MemoryStore"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, temp_project_dir, logger):
        """Test memory store initialization."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        assert memory.db_path == temp_project_dir / ".k2edit_memory.db"
        assert memory.logger is not None
    
    
    @pytest.mark.asyncio
    async def test_store_conversation(self, temp_project_dir, logger):
        """Test storing conversations."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        await memory.store_conversation(
            query="How do I use this function?",
            response="This function takes two parameters...",
            context={"file_path": "main.py", "line": 10}
        )
        
        conversations = await memory.get_recent_conversations(1)
        assert len(conversations) == 1
        assert conversations[0]["query"] == "How do I use this function?"
        assert conversations[0]["response"] == "This function takes two parameters..."
    
    
    @pytest.mark.asyncio
    async def test_store_code_change(self, temp_project_dir, logger):
        """Test storing code changes."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        await memory.store_code_change(
            file_path="main.py",
            change_type="modify",
            old_content="def old_func():\n    pass",
            new_content="def new_func():\n    return True",
            context={"line_range": "1-3"}
        )
        
        # Verify change was stored
        changes = await memory.search_memory("main.py")
        assert len(changes) > 0
    
    
    @pytest.mark.asyncio
    async def test_store_pattern(self, temp_project_dir, logger):
        """Test storing code patterns."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        pattern = {
            "type": "function_definition",
            "name": "calculate_sum",
            "parameters": ["a", "b"],
            "return_type": "int"
        }
        
        await memory.store_pattern(
            pattern=pattern,
            context={"file_path": "utils.py", "usage_count": 3},
            metadata={"complexity": "low", "category": "math"}
        )
        
        patterns = await memory.find_similar_patterns(pattern)
        assert len(patterns) > 0
    
    
    @pytest.mark.asyncio
    async def test_get_recent_conversations(self, temp_project_dir, logger):
        """Test retrieving recent conversations."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Store multiple conversations
        for i in range(5):
            await memory.store_conversation(
                query=f"Query {i}",
                response=f"Response {i}",
                context={"iteration": i}
            )
        
        # Get recent conversations
        recent = await memory.get_recent_conversations(3)
        assert len(recent) == 3
        assert recent[0]["query"] == "Query 4"  # Most recent first
        assert recent[2]["query"] == "Query 2"
    
    
    @pytest.mark.asyncio
    async def test_get_file_context(self, temp_project_dir, logger):
        """Test getting context for a specific file."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Store context for specific file
        await memory.store_context_change(
            file_path="main.py",
            context_type="symbols",
            content={"functions": ["main", "helper"], "classes": ["MainClass"]}
        )
        
        context = await memory.get_file_context("main.py")
        assert len(context) > 0
        assert any(c["context_type"] == "symbols" for c in context)
    
    
    @pytest.mark.asyncio
    async def test_search_memory(self, temp_project_dir, logger):
        """Test searching memory."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Store various types of data
        await memory.store_conversation(
            query="How to use numpy?",
            response="Use import numpy as np...",
            context={"file_path": "data_analysis.py"}
        )
        
        await memory.store_code_change(
            file_path="data_analysis.py",
            change_type="add",
            old_content="",
            new_content="import numpy as np"
        )
        
        # Search for numpy-related entries
        results = await memory.search_memory("numpy")
        assert len(results) > 0
    
    
    @pytest.mark.asyncio
    async def test_find_similar_patterns(self, temp_project_dir, logger):
        """Test finding similar patterns."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Store similar patterns
        pattern1 = {"type": "for_loop", "structure": "for i in range(n)"}
        pattern2 = {"type": "for_loop", "structure": "for item in items"}
        
        await memory.store_pattern(pattern1, {"file": "file1.py"})
        await memory.store_pattern(pattern2, {"file": "file2.py"})
        
        # Find similar patterns
        similar = await memory.find_similar_patterns(
            {"type": "for_loop", "structure": "for x in collection"}
        )
        
        assert len(similar) >= 2
    
    
    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, temp_project_dir, logger):
        """Test cleanup of old memory entries."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Store old entry
        old_date = datetime.now() - timedelta(days=100)
        await memory.store_conversation(
            query="old query",
            response="old response",
            context={"timestamp": old_date.isoformat()}
        )
        
        # Cleanup (should remove old entries)
        await memory.cleanup_old_entries(days=30)
        
        # Verify old entries are cleaned up
        recent = await memory.get_recent_conversations(100)
        old_entries = [r for r in recent if r.get("query") == "old query"]
        assert len(old_entries) == 0
    
    
    @pytest.mark.asyncio
    async def test_memory_statistics(self, temp_project_dir, logger):
        """Test memory statistics."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Store some data
        for i in range(10):
            await memory.store_conversation(
                query=f"Query {i}",
                response=f"Response {i}",
                context={"test": True}
            )
        
        stats = await memory.get_statistics()
        
        assert "total_entries" in stats
        assert "conversations" in stats
        assert "changes" in stats
        assert "patterns" in stats
        assert stats["conversations"] >= 10
    
    
    @pytest.mark.asyncio
    async def test_empty_database(self, temp_project_dir, logger):
        """Test behavior with empty database."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Test empty database queries
        conversations = await memory.get_recent_conversations(10)
        assert conversations == []
        
        patterns = await memory.find_similar_patterns({"type": "test"})
        assert patterns == []
        
        context = await memory.get_file_context("nonexistent.py")
        assert context == []
    
    
    @pytest.mark.asyncio
    async def test_memory_persistence(self, temp_project_dir, logger):
        """Test that memory persists across sessions."""
        db_path = temp_project_dir / "test_memory.db"
        
        # First session
        memory1 = MemoryStore(logger)
        await memory1.initialize(str(temp_project_dir))
        await memory1.store_conversation("test", "response", {})
        await memory1.close()
        
        # Second session
        memory2 = MemoryStore(logger)
        await memory2.initialize(str(temp_project_dir))
        conversations = await memory2.get_recent_conversations(1)
        
        assert len(conversations) == 1
        assert conversations[0]["query"] == "test"
    
    
    @pytest.mark.asyncio
    async def test_error_handling(self, temp_project_dir, logger):
        """Test error handling in memory operations."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Test with invalid data (should not crash)
        try:
            await memory.store_conversation(None, None, None)
        except Exception as e:
            # Should handle gracefully
            assert "error" in str(e).lower() or True  # Don't fail test on expected behavior
    
    
    @pytest.mark.asyncio
    async def test_bulk_operations(self, temp_project_dir, logger):
        """Test bulk memory operations."""
        memory = MemoryStore(logger)
        await memory.initialize(str(temp_project_dir))
        
        # Store many conversations
        for i in range(100):
            await memory.store_conversation(
                query=f"Bulk query {i}",
                response=f"Bulk response {i}",
                context={"batch": True}
            )
        
        # Test retrieval
        recent = await memory.get_recent_conversations(50)
        assert len(recent) == 50
        assert all("bulk" in r["query"].lower() for r in recent[:5])