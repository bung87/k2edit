#!/usr/bin/env python3
"""Test LSP client with proper settings configuration"""

import asyncio
from pathlib import Path
import pytest


from src.k2edit.agent.lsp_client import LSPClient
from src.k2edit.agent.language_configs import LanguageConfigs


@pytest.mark.asyncio
async def test_lsp_with_settings(logger):
    """Test LSP client with proper settings"""
    
    # Create LSP client
    lsp_client = LSPClient(logger=logger)
    
    # Get Python configuration with settings
    config = LanguageConfigs.get_config("python")
    print(f"Python config: {config}")
    
    project_root = Path.cwd()
    
    try:
        # Start the server
        print("Starting Python LSP server...")
        success = await lsp_client.start_server("python", config["command"], project_root)
        
        if not success:
            print("Failed to start LSP server")
            return
        
        print("LSP server started successfully")
        
        # Initialize connection with settings
        print("Initializing connection with settings...")
        init_success = await lsp_client.initialize_connection("python", project_root, config.get("settings"))
        
        if not init_success:
            print("Failed to initialize LSP connection")
            return
        
        print("LSP connection initialized successfully")
        
        # Wait a moment for initialization to complete
        await asyncio.sleep(1)
        
        # Open the test file
        test_file = Path("test_diagnostics.py")
        if test_file.exists():
            print(f"Opening test file: {test_file}")
            await lsp_client.notify_file_opened("python", str(test_file.absolute()))
            
            # Wait for diagnostics
            await asyncio.sleep(2)
            
            # Get diagnostics
            diagnostics = await lsp_client.get_diagnostics("python", str(test_file.absolute()))
            print(f"Diagnostics for {test_file}: {diagnostics}")
            
            if diagnostics:
                print(f"Found {len(diagnostics)} diagnostic(s):")
                for i, diag in enumerate(diagnostics, 1):
                    print(f"  {i}. {diag}")
            else:
                print("No diagnostics found")
        else:
            print(f"Test file {test_file} not found")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            await lsp_client.stop_server("python")
            print("LSP server stopped")
        except Exception as e:
            print(f"Error stopping server: {e}")

if __name__ == "__main__":
    asyncio.run(test_lsp_with_settings())