#!/usr/bin/env python3
"""
Example: Using ChromaDB as an alternative to SQLite for K2Edit memory storage

This example demonstrates how to configure K2Edit to use ChromaDB instead of SQLite
for native vector embedding support, which can resolve the "fds_to_keep" error on macOS.
"""

import os
import asyncio
import logging
from pathlib import Path

# Set environment variable to use ChromaDB

# Import after setting environment variable
from agent.context_manager import AgenticContextManager
from agent.memory_config import MemoryStoreConfig, create_memory_store


async def main():
    """Demonstrate ChromaDB usage"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create context manager (will automatically use ChromaDB based on env var)
    context_manager = AgenticContextManager(logger)
    
    # Initialize with current directory
    project_root = str(Path.cwd())
    await context_manager.initialize(project_root)
    
    logger.info(f"Memory store type: {type(context_manager.memory_store).__name__}")
    
    # Test storing and retrieving data
    await test_memory_operations(context_manager, logger)
    
    logger.info("ChromaDB example completed successfully!")


async def test_memory_operations(context_manager, logger):
    """Test basic memory operations with ChromaDB"""
    memory_store = context_manager.memory_store
    
    # Store a conversation
    await memory_store.store_conversation({
        "query": "How do I use ChromaDB with K2Edit?",
        "context": {"file_path": "examples/chromadb_example.py"}
    })
    logger.info("Stored conversation in ChromaDB")
    
    # Store code context
    await memory_store.store_context("examples/chromadb_example.py", {
        "language": "python",
        "symbols": ["main", "test_memory_operations"],
        "dependencies": ["asyncio", "logging", "pathlib"]
    })
    logger.info("Stored code context in ChromaDB")
    
    # Store a code pattern
    await memory_store.store_pattern(
        "async_function",
        "async def main():\n    pass",
        {"language": "python", "category": "async"}
    )
    logger.info("Stored code pattern in ChromaDB")
    
    # Perform semantic search
    results = await memory_store.semantic_search("ChromaDB usage", limit=3)
    logger.info(f"Semantic search returned {len(results)} results")
    
    for i, result in enumerate(results):
        logger.info(f"Result {i+1}: {result.get('metadata', {}).get('type', 'unknown')} (similarity: {result.get('similarity', 0):.3f})")
    
    # Find similar code
    similar_code = await memory_store.find_similar_code("async def", limit=2)
    logger.info(f"Found {len(similar_code)} similar code patterns")
    
    # Get recent conversations
    recent = await memory_store.get_recent_conversations(limit=5)
    logger.info(f"Retrieved {len(recent)} recent conversations")


def demonstrate_configuration():
    """Show different ways to configure memory store"""
    print("\n=== ChromaDB Configuration Options ===")
    
    # Method 1: Environment variable
    print("\n1. Using Environment Variable:")
    print("   python main.py")
    
    # Method 2: Programmatic configuration
    print("\n2. Programmatic Configuration:")
    print("""
   from agent.memory_config import MemoryStoreConfig, create_memory_store
   
   config = MemoryStoreConfig(store_type="chromadb")
   memory_store = create_memory_store(context_manager, logger, config)
   """)
    
    # Method 3: Custom ChromaDB settings
    print("\n3. Custom ChromaDB Settings:")
    print("""
   config = MemoryStoreConfig(
       store_type="chromadb",
       chroma_settings={
           "anonymized_telemetry": False,
           "allow_reset": True
       }
   )
   """)
    
    print("\n=== Benefits of ChromaDB over SQLite ===")
    print("✓ Native vector embedding support")
    print("✓ Resolves macOS 'fds_to_keep' multiprocessing errors")
    print("✓ Better semantic search performance")
    print("✓ Scalable for large codebases")
    print("✓ Built-in similarity search")
    print("✓ No manual embedding storage/retrieval")
    
    print("\n=== Storage Locations ===")
    print("SQLite:   .k2edit/memory.db")
    print("ChromaDB: .k2edit/chroma_db/")


if __name__ == "__main__":
    # Show configuration options
    demonstrate_configuration()
    
    # Run the async example
    print("\n=== Running ChromaDB Example ===")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"\nExample failed: {e}")
        import traceback
        traceback.print_exc()