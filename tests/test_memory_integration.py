#!/usr/bin/env python3
"""
Test script to verify ChromaDB memory store integration
"""

import os
import sys
import asyncio
import tempfile
import shutil
from pathlib import Path
import pytest

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.k2edit.agent.memory_config import create_memory_store, MemoryStoreConfig
from src.k2edit.agent.chroma_memory_store import ChromaMemoryStore

class MockContextManager:
    """Mock context manager for testing"""
    async def _generate_embedding(self, content: str):
        # Return a simple mock embedding
        return [0.1] * 384

@pytest.mark.asyncio
async def test_chromadb_memory_store():
    """Test ChromaDB memory store functionality"""
    print("=== ChromaDB Memory Store Integration Test ===")
    print()
    
    print("=== Testing ChromaDB Memory Store ===")
    mock_context = MockContextManager()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create ChromaDB memory store
        memory_store = create_memory_store(mock_context)
        print(f"✓ Created ChromaDB memory store: {type(memory_store).__name__}")
        
        # Initialize and test basic operations
        await memory_store.initialize(temp_dir)
        
        # Store some test data
        await memory_store.store_conversation({
            "query": "test query",
            "response": "test response"
        })
        
        await memory_store.store_context("test.py", {
            "language": "python",
            "content": "def test(): pass"
        })
        
        # Retrieve data
        conversations = await memory_store.get_recent_conversations(limit=5)
        file_context = await memory_store.get_file_context("test.py")
        similar_code = await memory_store.find_similar_code("def test", limit=5)
        
        # Assertions
        assert len(conversations) == 1, f"Expected 1 conversation, got {len(conversations)}"
        assert file_context is not None, "Expected file context to be found"
        assert "context" in file_context, "Expected context data in file context"
        
        print("✓ Stored and retrieved data successfully")
        print(f"  - Conversations: {len(conversations)}")
        print(f"  - File context: {'Found' if file_context else 'Not found'}")
        print(f"  - Similar code: {len(similar_code)}")

# Removed environment configuration test as ChromaDB is now the only memory store

async def main():
    """Run ChromaDB memory store test"""
    try:
        await test_chromadb_memory_store()
        
        print()
        print("🎉 All ChromaDB memory store tests passed!")
        print()
        print("ChromaDB is now the default and only memory store for K2Edit.")
        print()
        print("Usage: python main.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)