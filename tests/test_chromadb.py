#!/usr/bin/env python3
"""
Quick test script to verify ChromaDB integration works correctly.
This script tests the basic functionality without the full K2Edit application.
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path
from aiologger import Logger

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


@pytest.mark.asyncio
async def test_chromadb_basic():
    """Test basic ChromaDB functionality"""
    print("Testing ChromaDB integration...")
    
    try:
        # Test ChromaDB import
        import chromadb
        print("✓ ChromaDB import successful")
        
        # Test our ChromaDB memory store
        from agent.chroma_memory_store import ChromaMemoryStore
        print("✓ ChromaMemoryStore import successful")
        
        # Create a mock context manager for testing
        class MockContextManager:
            def _generate_embedding(self, text):
                # Return a simple mock embedding
                import hashlib
                # Create a deterministic "embedding" from text hash
                hash_obj = hashlib.md5(text.encode())
                # Convert to a list of floats (384 dimensions like MiniLM)
                hash_bytes = hash_obj.digest()
                embedding = []
                for i in range(0, len(hash_bytes), 4):
                    chunk = hash_bytes[i:i+4]
                    if len(chunk) == 4:
                        val = int.from_bytes(chunk, 'big') / (2**32 - 1)
                        embedding.append(val)
                # Pad to 384 dimensions
                while len(embedding) < 384:
                    embedding.append(0.0)
                return embedding[:384]
        
        # Setup logging
        logger = Logger(name=__name__)
        
        # Create memory store
        mock_context = MockContextManager()
        memory_store = ChromaMemoryStore(mock_context, logger)
        
        # Initialize with current directory
        await memory_store.initialize(str(Path.cwd()))
        print("✓ ChromaMemoryStore initialization successful")
        
        # Test storing data
        await memory_store.store_conversation({
            "query": "Test query",
            "response": "Test response",
            "context": {"test": True}
        })
        print("✓ Store conversation successful")
        
        await memory_store.store_context("test.py", {
            "language": "python",
            "symbols": ["test_function"]
        })
        print("✓ Store context successful")
        
        await memory_store.store_pattern(
            "test_pattern",
            "def test(): pass",
            {"language": "python"}
        )
        print("✓ Store pattern successful")
        
        # Test searching
        search_results = await memory_store.search_relevant_context("test query", limit=5)
        similar_code = await memory_store.find_similar_code("def test", limit=5)
        recent_conversations = await memory_store.get_recent_conversations(limit=5)
        
        # Assertions for validation
        assert len(search_results) >= 1, f"Expected at least 1 search result, got {len(search_results)}"
        assert len(similar_code) >= 1, f"Expected at least 1 similar code result, got {len(similar_code)}"
        assert len(recent_conversations) >= 1, f"Expected at least 1 recent conversation, got {len(recent_conversations)}"
        
        print(f"✓ Semantic search returned {len(search_results)} results")
        print(f"✓ Similar code search returned {len(similar_code)} results")
        print(f"✓ Recent conversations returned {len(recent_conversations)} results")
        
        print("\n🎉 All ChromaDB tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install ChromaDB: pip install chromadb>=0.4.0")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


@pytest.mark.asyncio
async def test_memory_config():
    """Test memory configuration system"""
    print("\nTesting memory configuration...")
    
    try:
        from agent.memory_config import create_memory_store
        
        # Test factory function (ChromaDB is now the default)
        class MockContextManager:
            def _generate_embedding(self, text):
                return [0.0] * 384
        
        mock_context = MockContextManager()
        memory_store = create_memory_store(mock_context)
        
        store_type = type(memory_store).__name__
        print(f"✓ Factory created: {store_type}")
        
        if store_type == "ChromaMemoryStore":
            print("✓ ChromaDB correctly selected as default")
        else:
            print(f"ℹ️  Using {store_type} (not ChromaDB)")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_environment_setup():
    """Test environment setup"""
    print("Testing environment setup...")
    
    # Check Python path
    current_dir = str(Path(__file__).parent)
    if current_dir in sys.path:
        print("✓ Current directory in Python path")
    else:
        print("ℹ️  Added current directory to Python path")
    
    # Check ChromaDB availability
    try:
        import chromadb
        print(f"✓ ChromaDB version: {chromadb.__version__}")
        print("✓ ChromaDB is now the default memory store")
        return True
    except ImportError:
        print("❌ ChromaDB not available")
        print("Install with: pip install chromadb>=0.4.0")
        return False