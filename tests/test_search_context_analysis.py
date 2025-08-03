#!/usr/bin/env python3
"""
Test file to analyze search_relevant_context behavior in chroma_memory_store.py
This test examines whether the search method adds unnecessary context.
"""

import asyncio
import json
import logging
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import sys

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.chroma_memory_store import ChromaMemoryStore, MemoryEntry
from agent.context_manager import AgenticContextManager


class MockContextManager:
    """Mock context manager for testing"""
    def __init__(self):
        self.logger = logging.getLogger("test")
        
    def _generate_embedding(self, text: str):
        """Generate a simple mock embedding"""
        # Simple mock embedding - just hash the text and create a vector
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        return [hash_val % 1000 / 1000.0] * 384  # Mock 384-dim vector


async def test_search_relevant_context_behavior():
    """Test the search_relevant_context method to identify unnecessary context issues"""
    
    # Setup
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_context = MockContextManager()
        memory_store = ChromaMemoryStore(mock_context, logging.getLogger("test"))
        
        await memory_store.initialize(temp_dir)
        
        # Test data - create various types of context
        test_contexts = [
            {
                "type": "relevant",
                "content": {"code": "def calculate_total(items): return sum(items)", "description": "Simple calculation function"},
                "file_path": "/src/utils.py",
                "tags": ["function", "utility"]
            },
            {
                "type": "potentially_unnecessary",
                "content": {"code": "# This is just a comment", "description": "Simple comment"},
                "file_path": "/src/comments.py",
                "tags": ["comment", "documentation"]
            },
            {
                "type": "relevant",
                "content": {"code": "class DataProcessor: pass", "description": "Main processing class"},
                "file_path": "/src/processor.py",
                "tags": ["class", "main"]
            },
            {
                "type": "borderline",
                "content": {"code": "import os", "description": "Import statement"},
                "file_path": "/src/imports.py",
                "tags": ["import", "standard"]
            }
        ]
        
        # Store test contexts
        for ctx in test_contexts:
            await memory_store.store_context(
                ctx["file_path"], 
                ctx["content"]
            )
        
        # Test various queries
        test_queries = [
            "calculate total",
            "data processing",
            "python function",
            "import os",
            "comment",
            "nonexistent topic"
        ]
        
        print("=== Testing search_relevant_context behavior ===\n")
        
        for query in test_queries:
            print(f"Query: '{query}'")
            results = await memory_store.search_relevant_context(query, limit=5)
            
            print(f"  Found {len(results)} results")
            for i, result in enumerate(results):
                content = result["content"]
                metadata = result["metadata"]
                distance = result.get("distance", 0.0)
                
                print(f"    {i+1}. Distance: {distance:.3f}")
                print(f"       File: {metadata.get('file_path', 'unknown')}")
                print(f"       Type: {metadata.get('type', 'unknown')}")
                print(f"       Content preview: {str(content)[:100]}...")
                
                # Analyze if this might be unnecessary context
                is_potentially_unnecessary = (
                    distance > 0.8 or  # High distance = low relevance
                    len(str(content)) < 10 or  # Very short content
                    "# This is just a comment" in str(content)  # Comment-only content
                )
                
                if is_potentially_unnecessary:
                    print(f"       ⚠️  POTENTIALLY UNNECESSARY")
                else:
                    print(f"       ✅ LIKELY RELEVANT")
            
            print()
        
        # Test edge cases
        print("=== Testing edge cases ===")
        
        # Empty query
        empty_results = await memory_store.search_relevant_context("", limit=5)
        print(f"Empty query results: {len(empty_results)}")
        
        # Very specific query
        specific_results = await memory_store.search_relevant_context("calculate_total function implementation", limit=5)
        print(f"Specific query results: {len(specific_results)}")
        
        # Test with different limits
        limit_test = await memory_store.search_relevant_context("python", limit=1)
        print(f"Limit 1 results: {len(limit_test)}")
        
        limit_test_3 = await memory_store.search_relevant_context("python", limit=3)
        print(f"Limit 3 results: {len(limit_test_3)}")


async def analyze_context_quality():
    """Analyze the quality and relevance of stored context"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_context = MockContextManager()
        memory_store = ChromaMemoryStore(mock_context, logging.getLogger("test"))
        
        await memory_store.initialize(temp_dir)
        
        # Simulate realistic code contexts
        realistic_contexts = [
            # High-quality, relevant contexts
            {
                "file_path": "/src/main.py",
                "content": {
                    "function_signature": "def process_user_input(user_input: str) -> dict",
                    "description": "Main user input processing function",
                    "complexity": "high",
                    "dependencies": ["validation", "parsing"]
                }
            },
            {
                "file_path": "/src/validation.py",
                "content": {
                    "class_definition": "class InputValidator:",
                    "description": "Validates user input for security and format",
                    "complexity": "medium"
                }
            },
            
            # Potentially low-quality contexts
            {
                "file_path": "/src/utils.py",
                "content": {
                    "comment": "# TODO: implement this later",
                    "description": "Placeholder comment"
                }
            },
            {
                "file_path": "/src/temp.py",
                "content": {
                    "temp_var": "x = 1",
                    "description": "Temporary variable"
                }
            }
        ]
        
        for ctx in realistic_contexts:
            await memory_store.store_context(ctx["file_path"], ctx["content"])
        
        print("=== Context Quality Analysis ===")
        
        # Analyze stored memories
        all_memories = memory_store.collections["memories"].get()
        print(f"Total memories stored: {len(all_memories['ids'])}")
        
        for i, doc_id in enumerate(all_memories["ids"]):
            content = json.loads(all_memories["documents"][i])
            metadata = all_memories["metadatas"][i]
            
            # Quality scoring
            content_str = str(content)
            quality_score = 0
            
            # Length-based scoring
            if len(content_str) > 50:
                quality_score += 1
            
            # Semantic value scoring
            if any(keyword in content_str.lower() for keyword in ["function", "class", "def", "import"]):
                quality_score += 2
            
            # Negative scoring for low-value content
            if any(negative in content_str.lower() for negative in ["todo", "temp", "placeholder"]):
                quality_score -= 2
            
            print(f"Memory {i+1}: Quality Score {quality_score}")
            print(f"  Content: {content}")
            print(f"  File: {metadata.get('file_path', 'unknown')}")
            print()


async def main():
    """Run all tests"""
    logging.basicConfig(level=logging.INFO)
    
    print("Testing ChromaMemoryStore search_relevant_context behavior...")
    await test_search_relevant_context_behavior()
    print("\n" + "="*60 + "\n")
    await analyze_context_quality()


if __name__ == "__main__":
    asyncio.run(main())