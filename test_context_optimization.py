#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from k2edit.agent.context_manager import AgenticContextManager
from k2edit.logger import setup_logging

async def test_context_optimization():
    """Test the optimized context manager to see token usage reduction"""
    print("Testing optimized context manager...")
    
    logger = setup_logging('INFO')
    manager = AgenticContextManager(logger=logger)
    
    # Initialize with current project
    project_root = Path(__file__).parent
    await manager.initialize(str(project_root))
    
    # Test with a simple query (should not include full project overview)
    print("\n=== Testing specific query (should be lightweight) ===")
    context = await manager.get_enhanced_context('help me understand this code')
    
    print(f'Context keys: {list(context.keys())}')
    
    # Estimate total size
    import json
    context_json = json.dumps(context, default=str)
    total_chars = len(context_json)
    estimated_tokens = total_chars // 4
    
    print(f'Total context size: {total_chars:,} characters')
    print(f'Estimated tokens: {estimated_tokens:,}')
    
    # Test with a general query (should include more context)
    print("\n=== Testing general project query (should include more context) ===")
    context2 = await manager.get_enhanced_context('give me a project overview')
    
    context2_json = json.dumps(context2, default=str)
    total_chars2 = len(context2_json)
    estimated_tokens2 = total_chars2 // 4
    
    print(f'Total context size: {total_chars2:,} characters')
    print(f'Estimated tokens: {estimated_tokens2:,}')
    
    # Compare with the problematic 2.6M tokens from the log
    print(f"\n=== Comparison with previous issue ===")
    print(f"Previous issue: ~2,664,198 tokens")
    print(f"Current specific query: ~{estimated_tokens:,} tokens ({(estimated_tokens/2664198)*100:.2f}% of previous)")
    print(f"Current general query: ~{estimated_tokens2:,} tokens ({(estimated_tokens2/2664198)*100:.2f}% of previous)")
    
    if estimated_tokens < 50000:  # Well under the 150k limit
        print("✅ SUCCESS: Context size is now manageable!")
    else:
        print("⚠️  WARNING: Context size is still quite large")

if __name__ == "__main__":
    asyncio.run(test_context_optimization())