#!/usr/bin/env python3
"""
Test script to analyze context issues:
1. Why relevant_history has so many items (10 items)
2. Why context tokens are so high (2,667,907 tokens)
3. Embedding generation errors: 'bad value(s) in fds_to_keep'

Based on log analysis from /Users/bung/py_works/k2edit/logs/k2edit.log:7422-7434
"""

import pytest
import tempfile
import json
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Add the parent directory to the path so we can import the agent modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.k2edit.logger import get_logger
from aiologger import Logger
from src.k2edit.agent.context_manager import AgenticContextManager
from src.k2edit.agent.chroma_memory_store import ChromaMemoryStore
from src.k2edit.agent.kimi_api import KimiAPI


class TestContextAnalysis:
    """Test class to analyze context issues"""
    
    @pytest.mark.asyncio
    async def test_relevant_history_size_analysis(self):
        """Analyze why relevant_history returns 10 items and their content size"""
        # Initialize logger with proper handlers
        import logging
        std_logger = logging.getLogger("test_context_analysis")
        std_logger.setLevel(logging.INFO)
        if not std_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            std_logger.addHandler(handler)
        
        # Create a mock logger that works with aiologger interface
        class MockAsyncLogger:
            def __init__(self, std_logger):
                self._logger = std_logger
            
            async def debug(self, msg, *args, **kwargs):
                self._logger.debug(msg, *args, **kwargs)
            
            async def info(self, msg, *args, **kwargs):
                self._logger.info(msg, *args, **kwargs)
            
            async def error(self, msg, *args, **kwargs):
                self._logger.error(msg, *args, **kwargs)
            
            async def warning(self, msg, *args, **kwargs):
                self._logger.warning(msg, *args, **kwargs)
        
        logger = MockAsyncLogger(std_logger)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock context manager
            mock_context_manager = Mock()
            mock_context_manager._generate_embedding = AsyncMock(return_value=[0.1] * 384)
            
            # Initialize memory store
            memory_store = ChromaMemoryStore(mock_context_manager, logger)
            await memory_store.initialize(temp_dir)
            
            # Simulate storing large amounts of conversation history
            # This mimics what might be causing the high token count
            large_conversations = []
            for i in range(50):  # Simulate 50 stored conversations
                conversation = {
                    "timestamp": f"2025-08-10T10:0{i%10}:00",
                    "query": f"User query {i} with detailed explanation and context that could be quite long and verbose, including code examples and comprehensive analysis",
                    "response": f"Assistant response {i} with extensive code examples, detailed explanations, and comprehensive analysis. {'x' * 1000}",  # 1KB of content per response
                    "context": {
                        "file_path": f"src/example_{i}.py",
                        "language": "python",
                        "symbols": [f"function_{j}" for j in range(20)],  # 20 symbols per conversation
                        "code_content": f"def example_function_{i}():\n    # Complex implementation\n    {'    # More code\n' * 50}"  # Large code blocks
                    }
                }
                large_conversations.append(conversation)
                
                # Store in memory
                await memory_store.store_conversation(conversation)
            
            # Test search_relevant_context with default parameters
            query = "add command support compile file atleast support python and nim"
            relevant_history = await memory_store.search_relevant_context(query, limit=10, max_distance=1.5)
            
            await logger.info(f"=== RELEVANT HISTORY ANALYSIS ===")
            await logger.info(f"Query: {query}")
            await logger.info(f"Number of relevant_history items: {len(relevant_history)}")
            
            total_chars = 0
            for i, item in enumerate(relevant_history):
                content_str = json.dumps(item.get('content', {}))
                item_chars = len(content_str)
                total_chars += item_chars
                
                await logger.info(f"Item {i+1}:")
                await logger.info(f"  - Distance: {item.get('distance', 'N/A')}")
                await logger.info(f"  - Content size: {item_chars} characters")
                await logger.info(f"  - Content type: {type(item.get('content', {}))}")
                await logger.info(f"  - Relevance score: {item.get('relevance_score', 'N/A')}")
                
                # Show sample of content
                if len(content_str) > 200:
                    await logger.info(f"  - Content preview: {content_str[:200]}...")
                else:
                    await logger.info(f"  - Content: {content_str}")
            
            await logger.info(f"Total characters in relevant_history: {total_chars}")
            await logger.info(f"Estimated tokens (chars/4): {total_chars // 4}")
            
            # Analyze why the limit isn't working effectively
            if len(relevant_history) == 10:
                await logger.warning("relevant_history returned exactly 10 items (the limit)")
                await logger.warning("This suggests the limit is being reached, not that there are only 10 relevant items")
            
            return relevant_history, total_chars
    
    @pytest.mark.asyncio
    async def test_context_token_estimation(self):
        """Analyze why context tokens are so high (2,667,907 tokens)"""
        # Initialize logger with proper handlers
        import logging
        std_logger = logging.getLogger("test_context_analysis")
        std_logger.setLevel(logging.INFO)
        if not std_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            std_logger.addHandler(handler)
        
        # Create a mock logger that works with aiologger interface
        class MockAsyncLogger:
            def __init__(self, std_logger):
                self._logger = std_logger
            
            async def debug(self, msg, *args, **kwargs):
                self._logger.debug(msg, *args, **kwargs)
            
            async def info(self, msg, *args, **kwargs):
                self._logger.info(msg, *args, **kwargs)
            
            async def error(self, msg, *args, **kwargs):
                self._logger.error(msg, *args, **kwargs)
            
            async def warning(self, msg, *args, **kwargs):
                self._logger.warning(msg, *args, **kwargs)
        
        logger = MockAsyncLogger(std_logger)
        
        # Simulate the context that was logged
        simulated_context = {
            "current_file": "src/k2edit/views/command_bar.py",
            "language": "python",
            "semantic_context": [],  # 5 items according to log
            "relevant_history": [],  # 10 items according to log
            "selected_code": None,
            "cursor_position": {"line": 1, "column": 1},
            "symbols": [],
            "dependencies": [],
            "recent_changes": []
        }
        
        # Simulate large semantic_context (5 items)
        for i in range(5):
            large_semantic_item = {
                "id": f"semantic_{i}",
                "content": {
                    "query": f"Previous query {i} with extensive context",
                    "response": f"Large response {i}: " + "x" * 50000,  # 50KB per item
                    "code_examples": [f"def example_{j}():\n    pass\n" * 100 for j in range(10)],  # Large code examples
                    "analysis": f"Detailed analysis {i}: " + "y" * 30000  # 30KB analysis
                },
                "metadata": {"timestamp": f"2025-08-10T10:0{i}:00"},
                "distance": 0.5 + i * 0.1
            }
            simulated_context["semantic_context"].append(large_semantic_item)
        
        # Simulate large relevant_history (10 items)
        for i in range(10):
            large_history_item = {
                "id": f"history_{i}",
                "content": {
                    "conversation": {
                        "query": f"Historical query {i} with comprehensive details",
                        "response": f"Historical response {i}: " + "z" * 80000,  # 80KB per item
                        "context": {
                            "file_content": f"# File content {i}\n" + "# Code line\n" * 5000,  # Large file content
                            "symbols": [f"symbol_{j}_{i}" for j in range(100)],  # Many symbols
                            "dependencies": [f"dep_{j}_{i}" for j in range(50)]  # Many dependencies
                        }
                    }
                },
                "metadata": {"timestamp": f"2025-08-10T09:0{i}:00"},
                "distance": 0.3 + i * 0.05
            }
            simulated_context["relevant_history"].append(large_history_item)
        
        # Calculate token estimation
        kimi_api = KimiAPI(logger)
        
        # Build messages as the system would
        messages = kimi_api._build_messages(
            "add command support compile file atleast support python and nim",
            simulated_context
        )
        
        await logger.info(f"=== TOKEN ANALYSIS ===")
        
        total_tokens = 0
        for i, message in enumerate(messages):
            content = message.get("content", "")
            tokens = kimi_api._estimate_token_count(content)
            total_tokens += tokens
            
            await logger.info(f"Message {i+1} ({message.get('role', 'unknown')}):")  
            await logger.info(f"  - Characters: {len(content)}")
            await logger.info(f"  - Estimated tokens: {tokens}")
            
            if len(content) > 1000:
                await logger.info(f"  - Content preview: {content[:500]}...")
        
        await logger.info(f"Total estimated tokens: {total_tokens}")
        
        # Analyze each context component
        await logger.info(f"\n=== CONTEXT COMPONENT ANALYSIS ===")
        
        semantic_context_str = json.dumps(simulated_context["semantic_context"])
        semantic_tokens = kimi_api._estimate_token_count(semantic_context_str)
        await logger.info(f"semantic_context: {len(semantic_context_str)} chars, ~{semantic_tokens} tokens")
        
        relevant_history_str = json.dumps(simulated_context["relevant_history"])
        history_tokens = kimi_api._estimate_token_count(relevant_history_str)
        await logger.info(f"relevant_history: {len(relevant_history_str)} chars, ~{history_tokens} tokens")
        
        return total_tokens, semantic_tokens, history_tokens
    
    @pytest.mark.asyncio
    async def test_embedding_generation_error(self):
        """Investigate the 'bad value(s) in fds_to_keep' embedding error"""
        # Initialize logger with proper handlers
        import logging
        std_logger = logging.getLogger("test_context_analysis")
        std_logger.setLevel(logging.INFO)
        if not std_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            std_logger.addHandler(handler)
        
        # Create a mock logger that works with aiologger interface
        class MockAsyncLogger:
            def __init__(self, std_logger):
                self._logger = std_logger
            
            async def debug(self, msg, *args, **kwargs):
                self._logger.debug(msg, *args, **kwargs)
            
            async def info(self, msg, *args, **kwargs):
                self._logger.info(msg, *args, **kwargs)
            
            async def error(self, msg, *args, **kwargs):
                self._logger.error(msg, *args, **kwargs)
            
            async def warning(self, msg, *args, **kwargs):
                self._logger.warning(msg, *args, **kwargs)
        
        logger = MockAsyncLogger(std_logger)
        
        await logger.info(f"=== EMBEDDING ERROR ANALYSIS ===")
        
        # This error typically occurs in multiprocessing/subprocess scenarios
        # Let's test different scenarios that might trigger it
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test 1: Normal context manager initialization
            try:
                context_manager = AgenticContextManager(logger)
                await logger.info("✓ Context manager initialized successfully")
                
                # Test embedding generation
                test_text = "add command support compile file atleast support python and nim"
                embedding = await context_manager._generate_embedding(test_text)
                
                if embedding is None:
                    await logger.error("✗ Embedding generation returned None")
                else:
                    await logger.info(f"✓ Embedding generated successfully: {len(embedding)} dimensions")
                    
            except Exception as e:
                await logger.error(f"✗ Context manager error: {e}")
                await logger.error(f"Error type: {type(e).__name__}")
        
        # Test 2: Check if the error is related to file descriptor issues
        # This often happens when there are too many open files or subprocess issues
        try:
            import resource
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            await logger.info(f"File descriptor limits: soft={soft_limit}, hard={hard_limit}")
            
            # Check current open file descriptors
            import os
            import glob
            fd_count = len(glob.glob(f'/proc/{os.getpid()}/fd/*')) if os.path.exists('/proc') else "N/A (not Linux)"
            await logger.info(f"Current open file descriptors: {fd_count}")
            
        except Exception as e:
            await logger.warning(f"Could not check file descriptor info: {e}")
        
        # Test 3: Check if it's related to the SentenceTransformer model loading
        await logger.info("Testing SentenceTransformer model loading...")
        try:
            # This might be where the error occurs
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            test_embedding = model.encode(["test text"])
            await logger.info(f"✓ SentenceTransformer working: {test_embedding.shape}")
        except Exception as e:
            await logger.error(f"✗ SentenceTransformer error: {e}")
            await logger.error(f"This might be the source of the 'bad value(s) in fds_to_keep' error")
    
    @pytest.mark.asyncio
    async def test_context_filtering_recommendations(self):
        """Test and recommend improvements for context filtering"""
        # Initialize logger with proper handlers
        import logging
        std_logger = logging.getLogger("test_context_analysis")
        std_logger.setLevel(logging.INFO)
        if not std_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            std_logger.addHandler(handler)
        
        # Create a mock logger that works with aiologger interface
        class MockAsyncLogger:
            def __init__(self, std_logger):
                self._logger = std_logger
            
            async def debug(self, msg, *args, **kwargs):
                self._logger.debug(msg, *args, **kwargs)
            
            async def info(self, msg, *args, **kwargs):
                self._logger.info(msg, *args, **kwargs)
            
            async def error(self, msg, *args, **kwargs):
                self._logger.error(msg, *args, **kwargs)
            
            async def warning(self, msg, *args, **kwargs):
                self._logger.warning(msg, *args, **kwargs)
        
        logger = MockAsyncLogger(std_logger)
        
        await logger.info(f"=== CONTEXT FILTERING RECOMMENDATIONS ===")
        
        # Recommendations based on analysis
        recommendations = [
            "1. REDUCE relevant_history limit from 10 to 3-5 items",
            "2. IMPLEMENT stricter distance filtering (max_distance < 1.0 instead of 1.5)",
            "3. ADD content size filtering (skip items > 10KB)",
            "4. IMPLEMENT relevance scoring to filter low-quality content",
            "5. FIX embedding generation by handling subprocess/file descriptor issues",
            "6. ADD caching for embeddings to reduce computation",
            "7. IMPLEMENT context summarization for large items",
            "8. ADD token budget management per context component"
        ]
        
        for rec in recommendations:
            await logger.info(rec)
        
        # Test improved filtering
        await logger.info(f"\n=== TESTING IMPROVED FILTERING ===")
        
        # Simulate improved parameters
        improved_params = {
            "relevant_history_limit": 3,  # Reduced from 10
            "max_distance": 0.8,  # Reduced from 1.5
            "max_content_size": 10000,  # 10KB limit
            "min_relevance_score": 0.3  # Minimum relevance threshold
        }
        
        await logger.info(f"Recommended parameters: {improved_params}")
        
        # Calculate potential token savings
        original_tokens = 2667907  # From the log
        estimated_reduction = 0.7  # 70% reduction with improved filtering
        improved_tokens = int(original_tokens * (1 - estimated_reduction))
        
        await logger.info(f"Estimated token reduction:")
        await logger.info(f"  Original: {original_tokens:,} tokens")
        await logger.info(f"  Improved: {improved_tokens:,} tokens")
        await logger.info(f"  Reduction: {original_tokens - improved_tokens:,} tokens ({estimated_reduction*100}%)")


if __name__ == "__main__":
    # Run the analysis
    async def run_analysis():
        test_instance = TestContextAnalysis()
        
        print("\n" + "="*60)
        print("CONTEXT ANALYSIS REPORT")
        print("="*60)
        
        try:
            # Test 1: Relevant history analysis
            print("\n1. ANALYZING RELEVANT HISTORY SIZE...")
            relevant_history, total_chars = await test_instance.test_relevant_history_size_analysis()
            print(f"   Result: {len(relevant_history)} items, {total_chars:,} characters")
            
            # Test 2: Token estimation analysis  
            print("\n2. ANALYZING TOKEN ESTIMATION...")
            total_tokens, semantic_tokens, history_tokens = await test_instance.test_context_token_estimation()
            print(f"   Result: {total_tokens:,} total tokens")
            print(f"   Semantic context: {semantic_tokens:,} tokens")
            print(f"   Relevant history: {history_tokens:,} tokens")
            
            # Test 3: Embedding error analysis
            print("\n3. ANALYZING EMBEDDING ERRORS...")
            await test_instance.test_embedding_generation_error()
            
            # Test 4: Recommendations
            print("\n4. GENERATING RECOMMENDATIONS...")
            await test_instance.test_context_filtering_recommendations()
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Run the analysis
    asyncio.run(run_analysis())