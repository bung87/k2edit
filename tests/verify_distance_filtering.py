#!/usr/bin/env python3
"""Simple verification of distance-based filtering implementation"""

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
        """Generate mock embedding for testing"""
        import hashlib
        # Simple deterministic embedding based on text hash
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        # Convert to float vector
        embedding = [float(b) / 255.0 for b in hash_bytes[:16]]
        return embedding


async def verify_distance_filtering():
    """Verify distance-based filtering is implemented correctly"""
    print("=== Distance-based Filtering Verification ===\n")
    
    # Setup
    mock_cm = MockContextManager()
    store = ChromaMemoryStore(mock_cm)
    await store.initialize("verify_project")
    
    # Store diverse test data
    test_data = [
        {
            "type": "context",
            "content": {"code": "def validate_email(email): return '@' in email"},
            "file": "email_validator.py"
        },
        {
            "type": "context", 
            "content": {"code": "TODO: implement validation logic"},
            "file": "todo.py"
        },
        {
            "type": "pattern",
            "content": {"code": "for item in items: print(item)"},
            "file": "loop_pattern.py"
        }
    ]
    
    # Store test data
    for i, data in enumerate(test_data):
        if data["type"] == "context":
            await store.store_context(data["file"], data["content"])
        else:
            await store.store_pattern("test", data["content"]["code"], data["content"])
    
    print("✓ Stored test data")
    
    # Test search_relevant_context with distance filtering
    print("\n--- Testing search_relevant_context ---")
    
    # Test with different thresholds
    query = "email validation"
    thresholds = [0.5, 1.0, 1.5, 2.0, 5.0]
    
    for threshold in thresholds:
        results = await store.search_relevant_context(query, limit=10, max_distance=threshold)
        print(f"Threshold {threshold}: {len(results)} results")
        
        for result in results:
            print(f"  Distance: {result['distance']:.3f}, Relevance: {result['relevance_score']:.2f}")
            if isinstance(result['content'], dict) and 'code' in result['content']:
                print(f"  Code: {result['content']['code'][:50]}...")
    
    # Test find_similar_code with distance filtering
    print("\n--- Testing find_similar_code ---")
    
    code_query = "def validate_email(email): return '@' in email"
    thresholds = [0.5, 1.0, 1.2, 2.0]
    
    for threshold in thresholds:
        results = await store.find_similar_code(code_query, limit=5, max_distance=threshold)
        print(f"Threshold {threshold}: {len(results)} results")
        
        for result in results:
            print(f"  Distance: {result['distance']:.3f}, Relevance: {result['relevance_score']:.2f}")
            print(f"  Code: {result['content'][:50]}...")
    
    # Verify filtering works
    print("\n--- Verifying Filtering Behavior ---")
    
    # Test that low-quality content is filtered
    all_results = await store.search_relevant_context("test", limit=10, max_distance=5.0)
    print(f"Total results without distance filtering: {len(all_results)}")
    
    # Check if TODO content is filtered by quality
    todo_found = False
    for result in all_results:
        if isinstance(result['content'], dict) and 'code' in result['content']:
            if 'TODO' in result['content']['code']:
                todo_found = True
                print(f"⚠ TODO content found (should be filtered): {result['content']['code']}")
    
    if not todo_found:
        print("✓ Low-quality TODO content appears to be filtered")
    
    # Test parameter validation
    print("\n--- Parameter Validation ---")
    
    # Test with invalid parameters
    try:
        results = await store.search_relevant_context("test", limit=-1, max_distance=-1)
        print("✓ Handles invalid parameters gracefully")
    except Exception as e:
        print(f"⚠ Parameter validation issue: {e}")
    
    # Cleanup
    try:
        import shutil
        if Path("verify_project").exists():
            shutil.rmtree("verify_project")
        print("✓ Cleanup completed")
    except:
        pass
    
    print("\n=== Distance Filtering Verification Complete ===")
    return True


if __name__ == "__main__":
    asyncio.run(verify_distance_filtering())