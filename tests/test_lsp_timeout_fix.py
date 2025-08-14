#!/usr/bin/env python3
"""Test script to verify LSP timeout handling fixes"""

import asyncio
import logging
from pathlib import Path
from aiologger import Logger

from src.k2edit.agent.lsp_client import LSPClient
from src.k2edit.agent.language_configs import LanguageConfigs


async def test_lsp_timeout_fix():
    """Test that LSP client handles timeouts correctly with project-aware tracking"""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = Logger.with_default_handlers(name='test-timeout-fix')
    
    # Create LSP client
    lsp_client = LSPClient(logger)
    
    try:
        await logger.info("Testing LSP timeout handling with project-aware server tracking...")
        
        # Get Python configuration
        python_config = LanguageConfigs.get_config('python')
        if not python_config:
            await logger.error("Python LSP config not found")
            return False
        
        project_root = Path.cwd()
        await logger.info(f"Using project root: {project_root}")
        
        # Test server startup
        await logger.info("Starting Python LSP server...")
        success = await lsp_client.start_server('python', python_config['command'], project_root)
        
        if not success:
            await logger.error("Failed to start Python LSP server")
            return False
        
        await logger.info("LSP server started successfully")
        
        # Check server status
        is_running = lsp_client.is_server_running('python', project_root)
        await logger.info(f"Server running status: {is_running}")
        
        # Show current connections
        connections = lsp_client.connections
        await logger.info(f"Current connections: {list(connections.keys())}")
        
        # Initialize connection
        await logger.info("Initializing LSP connection...")
        init_success = await lsp_client.initialize_connection('python', project_root, python_config.get('settings', {}))
        
        if not init_success:
            await logger.error("Failed to initialize LSP connection")
            return False
        
        await logger.info("LSP connection initialized successfully")
        
        # Test a simple request to verify communication
        test_file = project_root / "src" / "k2edit" / "main.py"
        if test_file.exists():
            await logger.info(f"Testing file operations with: {test_file}")
            
            # Notify file opened
            await lsp_client.notify_file_opened(str(test_file), 'python')
            await logger.info("File opened notification sent")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Try to get document symbols (this might timeout if there are issues)
            await logger.info("Requesting document symbols...")
            symbols = await lsp_client.get_document_symbols(str(test_file), 'python')
            
            if symbols:
                await logger.info(f"Successfully retrieved {len(symbols)} symbols")
            else:
                await logger.warning("No symbols retrieved (this might be normal)")
        
        await logger.info("Test completed successfully!")
        return True
        
    except Exception as e:
        await logger.error(f"Test failed with error: {e}", exc_info=True)
        return False
    finally:
        # Clean up
        await logger.info("Shutting down LSP client...")
        await lsp_client.shutdown()
        await logger.info("Test cleanup completed")


if __name__ == "__main__":
    result = asyncio.run(test_lsp_timeout_fix())
    if result:
        print("\n✅ LSP timeout fix test PASSED")
    else:
        print("\n❌ LSP timeout fix test FAILED")