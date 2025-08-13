#!/usr/bin/env python3
"""
Test LSP message routing to ensure document symbol responses are handled correctly
"""

import asyncio
import logging
from pathlib import Path
from aiologger import Logger

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from k2edit.agent.lsp_client import LSPClient
from k2edit.agent.language_configs import LanguageConfigs

async def test_lsp_message_routing():
    """Test that LSP client properly routes document symbol responses"""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = Logger.with_default_handlers(name='test-message-routing')
    
    # Create LSP client
    lsp_client = LSPClient(logger)
    
    try:
        await logger.info("Starting LSP message routing test...")
        
        # Start Python LSP server
        language_configs = LanguageConfigs()
        python_config = language_configs.get_config('python')
        if not python_config:
            await logger.error("Python LSP config not found")
            return
        
        project_root = Path.cwd()
        success = await lsp_client.start_server('python', python_config['command'], project_root)
        
        if not success:
            await logger.error("Failed to start Python LSP server")
            return
        
        await logger.info("LSP server started successfully")
        
        # Initialize connection
        init_success = await lsp_client.initialize_connection('python', project_root, python_config.get('settings', {}))
        
        if not init_success:
            await logger.error("Failed to initialize LSP connection")
            return
        
        await logger.info("LSP connection initialized successfully")
        
        # Test file
        test_file = project_root / "src" / "k2edit" / "main.py"
        if not test_file.exists():
            await logger.error(f"Test file {test_file} does not exist")
            return
        
        # Notify file opened (this will trigger diagnostics)
        await lsp_client.notify_file_opened(str(test_file), 'python')
        await logger.info(f"Notified LSP about opened file: {test_file}")
        
        # Wait a bit for diagnostics to be processed
        await asyncio.sleep(2)
        
        # Now request document symbols
        await logger.info("Requesting document symbols...")
        symbols = await lsp_client.get_document_symbols(str(test_file), 'python')
        
        if symbols:
            await logger.info(f"SUCCESS: Received {len(symbols)} document symbols")
            for i, symbol in enumerate(symbols[:3]):
                name = symbol.get('name', 'unnamed')
                kind = symbol.get('kind', 'unknown')
                await logger.info(f"  Symbol {i+1}: {name} (kind: {kind})")
            if len(symbols) > 3:
                await logger.info(f"  ... and {len(symbols) - 3} more symbols")
        else:
            await logger.warning("No document symbols received")
        
        # Test multiple concurrent requests
        await logger.info("Testing concurrent document symbol requests...")
        tasks = []
        for i in range(3):
            task = asyncio.create_task(lsp_client.get_document_symbols(str(test_file), 'python'))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                await logger.error(f"Concurrent request {i+1} failed: {result}")
            elif result:
                success_count += 1
                await logger.info(f"Concurrent request {i+1} succeeded with {len(result)} symbols")
            else:
                await logger.warning(f"Concurrent request {i+1} returned no symbols")
        
        await logger.info(f"Concurrent test: {success_count}/3 requests succeeded")
        
    except Exception as e:
        await logger.error(f"Test failed with exception: {e}")
    
    finally:
        # Cleanup
        await logger.info("Shutting down LSP client...")
        await lsp_client.shutdown()
        await logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(test_lsp_message_routing())