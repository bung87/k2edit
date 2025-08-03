#!/usr/bin/env python3
"""Test script to verify embedding generation fix"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import asyncio
import logging
from agent.context_manager import AgenticContextManager

async def test_embedding_generation():
    """Test that embedding generation works without errors"""
    print("=== Testing Embedding Generation Fix ===")
    print()
    
    # Set up logging to capture any errors
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Create context manager
        context_manager = AgenticContextManager(logger)
        
        # Test embedding generation
        test_content = "This is a test string for embedding generation"
        print(f"Testing embedding generation for: '{test_content}'")
        
        embedding = context_manager._generate_embedding(test_content)
        
        if embedding and len(embedding) == 384:
            print(f"✓ Embedding generated successfully: {len(embedding)} dimensions")
            print(f"✓ First 5 values: {embedding[:5]}")
            return True
        else:
            print(f"✗ Embedding generation failed or wrong dimensions: {len(embedding) if embedding else 'None'}")
            return False
            
    except Exception as e:
        print(f"✗ Error during embedding generation: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_embedding_generation())
    if success:
        print("\n🎉 Embedding generation test passed!")
    else:
        print("\n❌ Embedding generation test failed!")
        sys.exit(1)