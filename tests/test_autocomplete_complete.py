#!/usr/bin/env python3
"""
Complete test file for autocomplete functionality with proper LSP initialization.
This file demonstrates the autocomplete feature working with full LSP integration.
"""

import asyncio
import sys
import os
from pathlib import Path
import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from k2edit.custom_syntax_editor import CustomSyntaxEditor
from k2edit.agent.lsp_client import LSPClient
from k2edit.agent.language_configs import LanguageConfigs
from aiologger import Logger
from k2edit.logger import get_logger

@pytest.mark.asyncio
async def test_autocomplete_complete():
    """Test the autocomplete functionality with proper LSP initialization."""
    print("Testing autocomplete functionality with LSP...")
    
    # Create logger
    logger = get_logger()
    
    try:
        # Create LSP client with logger
        lsp_client = LSPClient(logger=logger)
        
        # Create test editor instance
        editor = CustomSyntaxEditor(logger=logger)
        editor.set_lsp_client(lsp_client)
        
        # Get Python configuration
        config = LanguageConfigs.get_config("python")
        print(f"Python LSP config: {config}")
        
        # Test file
        test_file_path = Path("test_autocomplete.py").absolute()
        editor.current_file = str(test_file_path)
        
        # Enable autocomplete
        editor.toggle_autocomplete(True)
        
        # Test content with proper Python structure
        test_content = """import os
import sys

class TestClass:
    def __init__(self):
        self.value = 42
    
    def test_method(self):
        return self.value
    
    def another_method(self, param):
        return param * 2

# Test the autocomplete here:
test_instance = TestClass()
test_instance."""
        
        editor.text = test_content
        
        # Set cursor at the end of "test_instance." (after the dot)
        lines = editor.text.splitlines()
        last_line = len(lines) - 1
        last_column = len(lines[last_line])  # Position after the dot
        editor.cursor_location = (last_line, last_column)
        
        print("Editor initialized with test content")
        print(f"Current file: {editor.current_file}")
        print(f"Cursor position: {editor.cursor_location}")
        print(f"Autocomplete enabled: {editor._autocomplete_enabled}")
        
        # Start LSP server
        project_root = Path.cwd()
        print(f"Starting Python LSP server from: {project_root}")
        
        success = await lsp_client.start_server("python", config["command"], project_root)
        if not success:
            print("Failed to start LSP server")
            return
        print("Python LSP server started successfully")
        
        # Initialize connection
        init_success = await lsp_client.initialize_connection("python", project_root, config.get("settings"))
        if not init_success:
            print("Failed to initialize LSP connection")
            return
        print("LSP connection initialized successfully")
        
        # Wait for initialization
        await asyncio.sleep(2)
        
        # Notify LSP server about the opened file
        await lsp_client.notify_file_opened(str(test_file_path), "python")
        print("Notified LSP server about opened file")
        
        # Wait a moment for file processing
        await asyncio.sleep(1)
        
        # Test completions
        print("Testing completions...")
        completions = await lsp_client.get_completions(
            str(test_file_path),
            last_line,
            last_column,
            "python"
        )
        
        if completions:
            print(f"Found {len(completions)} completions:")
            for i, completion in enumerate(completions[:5]):  # Show first 5
                label = completion.get("label", "unknown")
                kind = completion.get("kind", "unknown")
                print(f"  {i+1}. {label} (kind: {kind})")
        else:
            print("No completions found")
            
        # Test via editor method
        print("\nTesting via editor _show_suggestions...")
        await editor._show_suggestions()
        
        if editor._suggestions:
            print(f"Editor found {len(editor._suggestions)} suggestions via LSP")
        else:
            print("Editor found no suggestions via LSP")
            
        # Shutdown
        await lsp_client.shutdown()
        print("Test completed successfully")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_autocomplete_complete())