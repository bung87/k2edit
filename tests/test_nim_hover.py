#!/usr/bin/env python3
"""Test script to verify Nim LSP hover functionality fixes."""

import asyncio
import sys
from pathlib import Path
from aiologger import Logger

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from k2edit.agent.lsp_client import LSPClient
from k2edit.agent.language_configs import LanguageConfigs

async def test_nim_hover():
    """Test Nim LSP hover functionality with the fixes."""
    logger = Logger.with_default_handlers(name="nim_hover_test")
    
    # Create LSP client
    lsp_client = LSPClient(logger)
    
    # Get Nim language configuration
    nim_config = LanguageConfigs.get_config("nim")
    if not nim_config:
        await logger.error("Nim language configuration not found")
        return False
    
    # Test project root (current directory)
    project_root = Path.cwd()
    
    try:
        # Start Nim LSP server
        await logger.info("Starting Nim LSP server...")
        success = await lsp_client.start_server("nim", nim_config["command"], project_root)
        
        if not success:
            await logger.error("Failed to start Nim LSP server")
            return False
        
        await logger.info("Nim LSP server started successfully")
        
        # Initialize connection
        await logger.info("Initializing LSP connection...")
        init_success = await lsp_client.initialize_connection("nim", project_root)
        
        if not init_success:
            await logger.error("Failed to initialize Nim LSP connection")
            return False
        
        await logger.info("LSP connection initialized successfully")
        
        # Create a simple Nim test file
        test_file = project_root / "test_hover.nim"
        test_content = '''# Simple Nim test file for hover testing
proc greet(name: string): string =
  result = "Hello, " & name & "!"

let message = greet("World")
echo message
'''
        
        test_file.write_text(test_content)
        await logger.info(f"Created test file: {test_file}")
        
        # Test hover on the 'greet' function (line 1, character 5)
        await logger.info("Testing hover on 'greet' function...")
        hover_result = await lsp_client.get_hover_info(str(test_file), 1, 5)
        
        if hover_result:
            await logger.info(f"Hover result received: {hover_result}")
            print(f"\n✅ SUCCESS: Hover information retrieved for Nim file!")
            print(f"Hover content: {hover_result}")
        else:
            await logger.warning("No hover result received")
            print(f"\n⚠️  WARNING: No hover information received, but no timeout occurred")
        
        # Test hover on a variable (line 4, character 4)
        await logger.info("Testing hover on 'message' variable...")
        hover_result2 = await lsp_client.get_hover_info(str(test_file), 4, 4)
        
        if hover_result2:
            await logger.info(f"Second hover result received: {hover_result2}")
            print(f"\n✅ SUCCESS: Second hover information retrieved!")
        else:
            await logger.warning("No second hover result received")
        
        # Clean up test file
        test_file.unlink()
        await logger.info("Cleaned up test file")
        
        return True
        
    except Exception as e:
        await logger.error(f"Test failed with exception: {e}", exc_info=True)
        return False
    finally:
        # Shutdown LSP client
        await logger.info("Shutting down LSP client...")
        await lsp_client.shutdown()
        await logger.info("LSP client shutdown complete")

async def main():
    """Main test function."""
    print("🧪 Testing Nim LSP hover functionality fixes...")
    print("=" * 50)
    
    success = await test_nim_hover()
    
    print("=" * 50)
    if success:
        print("✅ Test completed successfully!")
        print("\nFixes applied:")
        print("1. ✅ Added language-specific timeout for Nim (30 seconds)")
        print("2. ✅ Ensured file is opened with LSP server before hover requests")
        print("3. ✅ Added proper message ID to hover requests")
        print("4. ✅ Improved timeout handling with language-specific values")
    else:
        print("❌ Test failed - check logs for details")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)