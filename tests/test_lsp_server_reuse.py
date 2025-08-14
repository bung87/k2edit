#!/usr/bin/env python3
"""
Simple test to check LSP server reuse behavior
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from k2edit.agent.lsp_client import LSPClient
from k2edit.agent.language_configs import LanguageConfigs
from k2edit.utils.language_utils import detect_language_by_extension

class SimpleLogger:
    """Simple logger that prints to stdout"""
    async def info(self, msg, **kwargs):
        print(f"INFO: {msg}")
    
    async def error(self, msg, **kwargs):
        print(f"ERROR: {msg}")
    
    async def debug(self, msg, **kwargs):
        print(f"DEBUG: {msg}")
    
    async def warning(self, msg, **kwargs):
        print(f"WARNING: {msg}")

async def test_server_reuse():
    """Test LSP server reuse behavior"""
    logger = SimpleLogger()
    lsp_client = LSPClient(logger)
    
    project_root = Path("/Users/bung/py_works/k2edit")
    
    print("=== Testing LSP Server Reuse Behavior ===")
    print(f"Project root: {project_root}")
    print()
    
    # Test with Python files
    python_files = [
        project_root / "src" / "k2edit" / "main.py",
        project_root / "src" / "k2edit" / "logger.py",
    ]
    
    for i, file_path in enumerate(python_files):
        if not file_path.exists():
            print(f"⚠️  File does not exist: {file_path}")
            continue
            
        language = detect_language_by_extension(file_path.suffix)
        print(f"\nProcessing file {i+1}: {file_path.name} (language: {language})")
        
        # Check current server status
        is_running = lsp_client.is_server_running(language)
        print(f"  Server running before: {is_running}")
        
        # Show current connections
        connections = lsp_client.connections
        print(f"  Current connections: {list(connections.keys())}")
        
        if language in connections:
            conn = connections[language]
            print(f"  Connection status: {conn.status}")
            print(f"  Connection healthy: {conn.is_healthy()}")
            if conn.process:
                print(f"  Process PID: {conn.process.pid}")
                print(f"  Process returncode: {conn.process.returncode}")
        
        # Simulate what happens in main.py when opening a file
        if not is_running and language != "unknown":
            config = LanguageConfigs.get_config(language)
            if config:
                print(f"  Would start {language} server with command: {config['command']}")
                print(f"  This demonstrates the issue: new server would be started")
            else:
                print(f"  No config found for {language}")
        else:
            print(f"  Server already running - would be reused ✅")
    
    print("\n=== Analysis ===")
    print("The issue is in the logic flow:")
    print("1. File is opened")
    print("2. Language is detected by extension only")
    print("3. is_server_running(language) is checked")
    print("4. If no server for that language exists, a new one is started")
    print("5. The project_root is passed but not used for server identification")
    print()
    print("Expected behavior: Server should be identified by (language, project_root)")
    print("Current behavior: Server is identified by language only")
    
    # Show the key methods involved
    print("\n=== Key Methods Analysis ===")
    print("is_server_running() checks: language in self.connections")
    print("start_server() uses: language as key in self.connections")
    print("Missing: project_root consideration in server identification")

if __name__ == "__main__":
    asyncio.run(test_server_reuse())