#!/usr/bin/env python3
"""
Test script to demonstrate ChromaDB symbol caching in LSP indexer.

This script shows how the LSP indexer now caches file symbols in ChromaDB
using file absolute path and content hash to avoid rebuilding the index
every time.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from k2edit.agent.lsp_indexer import LSPIndexer
from k2edit.core.logger import Logger


async def test_symbol_caching():
    """Test the symbol caching functionality"""
    
    # Initialize logger
    logger = Logger()
    await logger.info("Starting symbol cache test...")
    
    # Initialize LSP indexer with current project
    project_root = Path(__file__).parent
    indexer = LSPIndexer(project_root, logger)
    
    try:
        # Initialize the indexer (this will set up ChromaDB cache)
        await indexer.initialize()
        
        # Get cache stats
        cache_stats = await indexer.get_cache_stats()
        await logger.info(f"Cache stats: {cache_stats}")
        
        # Test indexing a file (should cache symbols)
        test_file = project_root / "src" / "k2edit" / "agent" / "lsp_indexer.py"
        if test_file.exists():
            await logger.info(f"First indexing of {test_file.name} (should cache symbols)")
            await indexer.index_file(str(test_file))
            
            # Index the same file again (should use cached symbols)
            await logger.info(f"Second indexing of {test_file.name} (should use cache)")
            await indexer.index_file(str(test_file))
            
            # Get symbols to verify they were indexed
            symbols = await indexer.get_symbols(str(test_file))
            await logger.info(f"Retrieved {len(symbols)} symbols from {test_file.name}")
        else:
            await logger.warning(f"Test file {test_file} not found")
        
    except Exception as e:
        await logger.error(f"Error during symbol cache test: {e}")
    
    finally:
        # Clean shutdown
        await indexer.shutdown()
        await logger.info("Symbol cache test completed")


if __name__ == "__main__":
    asyncio.run(test_symbol_caching())