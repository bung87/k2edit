#!/usr/bin/env python3
"""
Test script to verify context truncation when limits are exceeded.
"""

import pytest
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the agent modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.k2edit.agent.kimi_api import KimiAPI

@pytest.mark.asyncio
async def test_context_truncation(logger):
    """Test context truncation when exceeding token limits."""
    
    # Initialize Kimi API
    kimi_api = KimiAPI(logger)
    
    # Create extremely large context that will definitely exceed the 150K token limit
    await logger.info("=== Test: Extremely Large Context (Should Trigger Truncation) ===")
    
    # Generate a massive file content (~24M characters = ~6M tokens, way over 150K limit)
    huge_content = "# This is a very large Python file with extensive documentation and code\n"
    
    # Build the content in parts to avoid f-string issues
    functions = []
    for i in range(10000):
        func_code = f"""def function_{i}():
    '''This is function {i} with detailed documentation: {'x' * 500}'''
    print('Function {i} executed')
    data_content = '{'y' * 200}'
    return {{'result': 'success', 'data': data_content}}
"""
        functions.append(func_code)
    
    huge_content += "\n".join(functions)
    
    # Create massive conversation history
    large_history = []
    for i in range(1000):
        large_history.append({
            "role": "user", 
            "content": f"This is user message {i} with extensive content and detailed questions about the codebase. Here's some context: {'a' * 1000}"
        })
        large_history.append({
            "role": "assistant", 
            "content": f"This is assistant response {i} with comprehensive explanation and code examples. Here's the detailed analysis: {'b' * 1500}"
        })
    
    huge_context = {
        "current_file": "extremely_large_file.py",
        "language": "python",
        "file_content": huge_content,
        "conversation_history": large_history,
        "selected_text": "selected code snippet that is also quite long: " + "z" * 5000,
        "semantic_context": [f"semantic_item_{i}_with_long_description_{'c' * 200}" for i in range(5000)],
        "relevant_history": {f"key_{i}": f"value_{i}_with_extensive_data_{'d' * 300}" for i in range(2000)},
        "similar_patterns": [f"pattern_{i}_with_detailed_explanation_{'e' * 400}" for i in range(3000)],
        "project_symbols": {f"symbol_{i}": f"definition_{i}_with_comprehensive_documentation_{'f' * 500}" for i in range(1500)}
    }
    
    await logger.info(f"Created huge context with file content: {len(huge_content)} characters")
    await logger.info(f"Conversation history: {len(large_history)} messages")
    
    # Estimate total size before processing
    total_chars = len(huge_content) + sum(len(str(msg)) for msg in large_history)
    estimated_tokens = total_chars // 4
    await logger.info(f"Estimated total tokens before processing: {estimated_tokens}")
    
    # Log the context details
    await kimi_api._log_context_details(huge_context, logger)
    
    # Build messages and validate
    huge_messages = kimi_api._build_messages("Please analyze this extremely large codebase and provide comprehensive insights about the architecture, patterns, and potential improvements", huge_context)
    
    await logger.info(f"Built {len(huge_messages)} messages before validation")
    
    # Calculate tokens before validation
    pre_validation_tokens = sum(kimi_api._estimate_token_count(msg.get("content", "")) for msg in huge_messages)
    await logger.info(f"Pre-validation estimated token count: {pre_validation_tokens}")
    
    # This should trigger truncation
    validated_huge_messages = await kimi_api._validate_context_length(huge_messages, logger)
    
    await logger.info(f"After validation: {len(validated_huge_messages)} messages")
    
    # Calculate final token count
    final_tokens = sum(kimi_api._estimate_token_count(msg.get("content", "")) for msg in validated_huge_messages)
    await logger.info(f"Final estimated token count: {final_tokens}")
    
    # Verify truncation worked (allow small margin for estimation errors)
    MAX_ALLOWED = 150100  # Small buffer for estimation errors
    if pre_validation_tokens > 150000 and final_tokens <= MAX_ALLOWED:
        await logger.info("✅ SUCCESS: Context was properly truncated from {} to {} tokens".format(pre_validation_tokens, final_tokens))
    elif pre_validation_tokens <= 150000:
        await logger.info("ℹ️  INFO: Context was already within limits, no truncation needed")
    else:
        await logger.error("❌ FAILURE: Context still exceeds limits after truncation ({} tokens)".format(final_tokens))
    
    await logger.info("\n=== Context Truncation Test Completed ===")
    await logger.info("Check 'test_context_truncation.log' for detailed output")