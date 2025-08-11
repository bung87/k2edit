#!/usr/bin/env python3
"""
Test script to verify context logging and validation in Kimi API integration.
"""

import pytest
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the agent modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.k2edit.agent.kimi_api import KimiAPI

@pytest.mark.asyncio
async def test_context_logging(logger):
    """Test context logging and validation."""
    
    # Initialize Kimi API
    kimi_api = KimiAPI(logger)
    
    # Test 1: Simple context
    await logger.info("=== Test 1: Simple Context ===")
    simple_context = {
        "current_file": "test.py",
        "language": "python",
        "file_content": "def hello():\n    print('Hello, World!')\n"
    }
    
    # Test the context logging without actually calling the API
    await kimi_api._log_context_details(simple_context, logger)
    
    # Test the message building and validation
    messages = kimi_api._build_messages("Review this code", simple_context)
    validated_messages = await kimi_api._validate_context_length(messages, logger)
    
    await logger.info(f"Original messages: {len(messages)}")
    await logger.info(f"Validated messages: {len(validated_messages)}")
    
    # Test 2: Large context that should trigger truncation
    await logger.info("\n=== Test 2: Large Context ===")
    large_content = "# Large file content\n" + "print('line')\n" * 50000  # ~600K characters
    large_context = {
        "current_file": "large_file.py",
        "language": "python",
        "file_content": large_content,
        "conversation_history": [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ],
        "selected_text": "selected code snippet",
        "semantic_context": ["context1", "context2", "context3"],
        "relevant_history": {"key1": "value1", "key2": "value2"}
    }
    
    await kimi_api._log_context_details(large_context, logger)
    
    large_messages = kimi_api._build_messages("Analyze this large file", large_context)
    validated_large_messages = await kimi_api._validate_context_length(large_messages, logger)
    
    await logger.info(f"Large messages: {len(large_messages)}")
    await logger.info(f"Validated large messages: {len(validated_large_messages)}")
    
    # Test 3: No context
    await logger.info("\n=== Test 3: No Context ===")
    await kimi_api._log_context_details(None, logger)
    
    no_context_messages = kimi_api._build_messages("Simple question", None)
    validated_no_context = await kimi_api._validate_context_length(no_context_messages, logger)
    
    await logger.info(f"No context messages: {len(no_context_messages)}")
    await logger.info(f"Validated no context: {len(validated_no_context)}")
    
    await logger.info("\n=== Context Logging Test Completed ===")
    await logger.info("Check 'test_context_logging.log' for detailed output")