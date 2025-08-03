#!/usr/bin/env python3
"""
Test to demonstrate improved context filtering for search_relevant_context
"""

import asyncio
import json
import logging
import tempfile
import re
from pathlib import Path
import sys

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.chroma_memory_store import ChromaMemoryStore, MemoryEntry


class MockContextManager:
    def __init__(self):
        self.logger = logging.getLogger("test")
        
    def _generate_embedding(self, text: str):
        # Simple mock embedding
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        return [hash_val % 1000 / 1000.0] * 384


def is_low_quality_content(content: dict) -> bool:
    """Determine if content is low quality/unnecessary"""
    content_str = str(content).lower()
    
    # Low-quality patterns
    low_quality_patterns = [
        r'^#.*$',  # Single-line comments
        r'^\s*$',  # Empty content
        r'^\w+\s*=\s*\d+$',  # Simple variable assignment
        r'^import\s+\w+(\s+as\s+\w+)?$',  # Simple imports
        r'^from\s+\w+\s+import\s+\w+$',  # Simple from imports
        r'^#\s*(todo|fixme|hack|xxx)',  # TODO/FIXME comments
        r'^print\(.*\)$',  # Debug print statements
        r'^console\.log\(.*\)$',  # Debug console logs
    ]
    
    for pattern in low_quality_patterns:
        if re.search(pattern, content_str, re.IGNORECASE):
            return True
    
    # Length-based filtering
    if len(content_str) < 15:
        return True
    
    # Content-based filtering
    if any(phrase in content_str for phrase in ["temporary", "placeholder", "stub"]):
        return True
    
    return False


def calculate_relevance_score(content: dict, query: str, distance: float) -> float:
    """Calculate relevance score for filtering"""
    content_str = str(content).lower()
    query_lower = query.lower()
    
    # Base score from distance (lower distance = higher score)
    distance_score = max(0, 1.0 - (distance / 100.0))  # Normalize distance
    
    # Keyword matching
    query_words = query_lower.split()
    content_words = content_str.split()
    
    keyword_matches = sum(1 for word in query_words if word in content_str)
    keyword_score = keyword_matches / max(len(query_words), 1)
    
    # Content quality score
    quality_score = 0
    if len(content_str) > 50:
        quality_score += 0.3
    if any(keyword in content_str for keyword in ["function", "class", "def", "method"]):
        quality_score += 0.4
    if "todo" in content_str or "fixme" in content_str:
        quality_score -= 0.5
    
    # Combine scores
    final_score = (distance_score * 0.4 + keyword_score * 0.4 + quality_score * 0.2)
    return max(0, final_score)


async def test_improved_filtering():
    """Test improved context filtering"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_context = MockContextManager()
        memory_store = ChromaMemoryStore(mock_context, logging.getLogger("test"))
        
        await memory_store.initialize(temp_dir)
        
        # Test data with varying quality
        test_contexts = [
            # High-quality contexts
            {
                "file_path": "/src/main.py",
                "content": {
                    "type": "function",
                    "name": "process_user_input",
                    "signature": "def process_user_input(user_input: str) -> dict",
                    "description": "Main function to process and validate user input",
                    "complexity": "high",
                    "dependencies": ["validation", "parsing", "error_handling"]
                }
            },
            {
                "file_path": "/src/validator.py",
                "content": {
                    "type": "class",
                    "name": "InputValidator",
                    "description": "Validates user input for security and format compliance",
                    "methods": ["validate_email", "validate_password", "sanitize_input"]
                }
            },
            
            # Low-quality contexts
            {
                "file_path": "/src/temp.py",
                "content": {
                    "type": "comment",
                    "text": "# TODO: implement this later"
                }
            },
            {
                "file_path": "/src/debug.py",
                "content": {
                    "type": "debug",
                    "code": "print('debug info')"
                }
            },
            {
                "file_path": "/src/simple.py",
                "content": {
                    "type": "variable",
                    "code": "x = 42"
                }
            },
            {
                "file_path": "/src/import.py",
                "content": {
                    "type": "import",
                    "code": "import os"
                }
            }
        ]
        
        # Store all contexts
        for ctx in test_contexts:
            await memory_store.store_context(ctx["file_path"], ctx["content"])
        
        # Test queries
        queries = ["user input processing", "validation", "python function"]
        
        print("=== Testing Improved Context Filtering ===\n")
        
        for query in queries:
            print(f"Query: '{query}'")
            
            # Get raw results
            raw_results = await memory_store.search_relevant_context(query, limit=10)
            
            # Apply filtering
            filtered_results = []
            for result in raw_results:
                content = result["content"]
                distance = result.get("distance", 0.0)
                
                # Skip low-quality content
                if is_low_quality_content(content):
                    continue
                
                # Calculate relevance score
                relevance_score = calculate_relevance_score(content, query, distance)
                
                # Only include relevant results
                if relevance_score > 0.3:  # Threshold
                    result["relevance_score"] = relevance_score
                    filtered_results.append(result)
            
            print(f"  Raw results: {len(raw_results)}")
            print(f"  Filtered results: {len(filtered_results)}")
            
            # Show comparison
            if filtered_results:
                print("  Top filtered results:")
                for i, result in enumerate(filtered_results[:3]):
                    content = result["content"]
                    score = result["relevance_score"]
                    print(f"    {i+1}. Score: {score:.2f}")
                    print(f"       Type: {content.get('type', 'unknown')}")
                    print(f"       File: {result['metadata'].get('file_path', 'unknown')}")
                    print(f"       Content: {str(content)[:80]}...")
            else:
                print("    No relevant results after filtering")
            
            print()


async def demonstrate_quality_thresholds():
    """Demonstrate different quality thresholds"""
    
    print("=== Quality Threshold Analysis ===")
    
    # Example content types with quality scores
    examples = [
        ("High-quality function", {
            "type": "function",
            "name": "process_data",
            "signature": "async def process_data(data: List[str]) -> dict",
            "description": "Processes input data with validation and error handling",
            "complexity": "high"
        }, 0.9),
        
        ("Medium-quality class", {
            "type": "class",
            "name": "DataHandler",
            "description": "Basic data handling class",
            "methods": ["load", "save"]
        }, 0.7),
        
        ("Low-quality comment", {
            "type": "comment",
            "text": "# TODO: add error handling"
        }, 0.1),
        
        ("Very low-quality", {
            "type": "variable",
            "code": "temp = 123"
        }, 0.0)
    ]
    
    for name, content, expected_score in examples:
        is_low = is_low_quality_content(content)
        score = calculate_relevance_score(content, "data processing", 10.0)
        
        print(f"{name}:")
        print(f"  Expected score: {expected_score}")
        print(f"  Calculated score: {score:.2f}")
        print(f"  Is low quality: {is_low}")
        print(f"  Content: {str(content)[:60]}...")
        print()


async def main():
    """Run all tests"""
    logging.basicConfig(level=logging.INFO)
    
    await test_improved_filtering()
    await demonstrate_quality_thresholds()


if __name__ == "__main__":
    asyncio.run(main())