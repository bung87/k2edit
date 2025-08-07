#!/usr/bin/env python3
"""Test distance-based filtering in ChromaMemoryStore"""

import pytest
import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.k2edit.agent.chroma_memory_store import ChromaMemoryStore


class MockContextManager:
    """Mock context manager for testing"""
    
    def __init__(self):
        self.logger = None
    
    def _generate_embedding(self, text: str):
        """Generate a simple mock embedding"""
        # Return a simple vector based on text length for testing
        import hashlib
        import numpy as np
        
        # Create a deterministic vector based on text content
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        vector = np.array([b / 255.0 for b in hash_bytes[:16]])
        return vector.tolist()


@pytest.mark.asyncio
async def test_distance_filtering():
    """Test distance-based filtering functionality"""
    print("Testing distance-based filtering...")
    
    # Setup
    mock_cm = MockContextManager()
    store = ChromaMemoryStore(mock_cm)
    await store.initialize("test_project")
    
    # Store some test memories with different content quality
    test_memories = [
        {
            "type": "context",
            "content": {
                "code": "def validate_user_input(data):\n    if not data.get('email'):\n        return False\n    if '@' not in data['email']:\n        return False\n    return True",
                "file": "validators.py"
            },
            "file_path": "validators.py"
        },
        {
            "type": "context", 
            "content": {
                "code": "// TODO: implement this later\ntemp_var = 42",
                "file": "temp.py"
            },
            "file_path": "temp.py"
        },
        {
            "type": "pattern",
            "content": {
                "code": "def process_list(items):\n    return [item.strip() for item in items if item.strip()]",
                "file": "utils.py"
            },
            "file_path": "utils.py"
        },
        {
            "type": "context",
            "content": {
                "code": "import os\nimport sys",
                "file": "imports.py"
            },
            "file_path": "imports.py"
        }
    ]
    
    # Store test memories
    for memory in test_memories:
        if memory["type"] == "context":
            await store.store_context(memory["file_path"], memory["content"])
        else:
            await store.store_pattern("utility", memory["content"]["code"], memory["content"])
    
    print("Stored test memories")
    
    # Test with different distance thresholds
    queries = ["user validation", "list processing", "imports"]
    thresholds = [0.5, 1.0, 1.5, 2.0]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        print("-" * 50)
        
        for threshold in thresholds:
            results = await store.search_relevant_context(query, limit=10, max_distance=threshold)
            
            print(f"Threshold {threshold}: {len(results)} results")
            for i, result in enumerate(results[:3]):  # Show top 3
                content_preview = str(result["content"])[:50] + "..."
                print(f"  {i+1}. Distance: {result['distance']:.3f}, "
                      f"Content: {content_preview}")
    
    # Test quality filtering
    print("\nQuality Filtering Test:")
    print("-" * 30)
    
    # Query that should filter out low-quality content
    results = await store.search_relevant_context("validation", limit=5, max_distance=2.0)
    
    high_quality = []
    low_quality = []
    
    for result in results:
        content = result["content"]
        if isinstance(content, dict) and "code" in content:
            code = content["code"]
            if "TODO" in code or "temp_var" in code or len(code.strip()) < 15:
                low_quality.append(result)
            else:
                high_quality.append(result)
    
    print(f"High quality results: {len(high_quality)}")
    print(f"Low quality results: {len(low_quality)}")
    
    for result in high_quality[:2]:
        print(f"  Good: {result['content']['code'][:60]}...")
    
    if low_quality:
        for result in low_quality[:2]:
            print(f"  Filtered: {result['content']['code'][:60]}...")
    
    # Cleanup
    try:
        import shutil
        test_path = Path("test_project") / ".k2edit"
        if test_path.exists():
            shutil.rmtree("test_project")
    except:
        pass
    
    print("\nDistance filtering test completed!")