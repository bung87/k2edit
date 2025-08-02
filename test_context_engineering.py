#!/usr/bin/env python3
"""
Test script to demonstrate the new context engineering and memory features.
"""

import asyncio
import os
import tempfile
from agent.memory_store import MemoryStore
from agent.context_manager import AgenticContextManager


async def test_enhanced_memory():
    """Test the new memory and context features"""
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Initialize memory store
        test_dir = "/tmp/test_project"
        os.makedirs(test_dir, exist_ok=True)
        memory_store = MemoryStore(db_path)
        await memory_store.initialize(test_dir)
        
        # Initialize context manager
        context_manager = AgenticContextManager()
        await context_manager.initialize(test_dir)
        
        # Create a test Python file
        test_code = '''
class Calculator:
    """A simple calculator class"""
    
    def __init__(self):
        self.history = []
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers"""
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
    
    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers"""
        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result

def main():
    calc = Calculator()
    print(calc.add(5, 3))
    print(calc.multiply(4, 7))

if __name__ == "__main__":
    main()
'''
        
        # Write test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp_file:
            tmp_file.write(test_code)
            test_file_path = tmp_file.name
        
        print("=== Testing Enhanced Memory and Context Features ===\n")
        
        # Store conversation memory
        await memory_store.store_conversation("User asked about calculator implementation")
        
        # Store context
        await memory_store.store_context(test_file_path, {
            'file_type': 'python',
            'classes': ['Calculator'],
            'functions': ['add', 'multiply', 'main']
        })
        
        # Store code pattern
        await memory_store.store_pattern(
            "def add(self, a: int, b: int) -> int:",
            "method",
            test_file_path,
            {'language': 'python', 'scope': 'Calculator.add'}
        )
        
        print("✓ Stored initial memories")
        
        # Test semantic search
        search_results = await memory_store.semantic_search("calculator add method", limit=5)
        print(f"✓ Semantic search found {len(search_results)} results")
        for result in search_results[:3]:
            print(f"  - {result['type']}: {result['content'][:50]}...")
        
        # Test enhanced context
        enhanced_context = await context_manager.get_enhanced_context(test_file_path, 15)
        print(f"\n✓ Enhanced context generated")
        print(f"  - File: {enhanced_context.file_path}")
        print(f"  - Code hierarchy: {len(enhanced_context.code_hierarchy)} elements")
        print(f"  - Semantic context: {len(enhanced_context.semantic_context)} items")
        
        # Test file structure analysis
        project_root = os.path.dirname(test_file_path)
        structure = await context_manager._analyze_file_structure(project_root)
        print(f"\n✓ File structure analyzed")
        print(f"  - Root: {structure['root']}")
        print(f"  - Files: {len(structure['files'])}")
        print(f"  - Languages: {structure['language_stats']}")
        
        # Test code hierarchy parsing
        with open(test_file_path, 'r') as f:
            content = f.read()
        hierarchy = context_manager._parse_code_hierarchy(content)
        print(f"\n✓ Code hierarchy parsed")
        for element in hierarchy:
            print(f"  - {element['type']}: {element['name']} (lines {element['start_line']}-{element['end_line']})")
        
        # Test memory relationships
        memories = await memory_store.search_relevant_context("calculator")
        if memories:
            memory_id = memories[0]['id']
            await memory_store.add_context_relationship(
                memory_id, memory_id, "self_reference", 1.0, {"test": True}
            )
            print(f"\n✓ Added memory relationship")
        
        # Cleanup
        os.unlink(test_file_path)
        
        print("\n=== All tests completed successfully! ===")
        
    finally:
        # Clean up database
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    asyncio.run(test_enhanced_memory())