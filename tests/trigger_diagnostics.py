#!/usr/bin/env python3
"""
Simple script to test LSP diagnostics
"""

import asyncio
import subprocess
import sys
import json
from pathlib import Path

async def test_pylsp_directly():
    """Test pylsp directly with the test file"""
    test_file = Path("test_diagnostics.py").absolute()
    
    if not test_file.exists():
        print(f"Test file {test_file} not found")
        return
    
    content = test_file.read_text()
    print(f"Testing file: {test_file}")
    print(f"Content length: {len(content)} characters")
    print("Content preview:")
    print(content[:200] + "..." if len(content) > 200 else content)
    print("\n" + "="*50 + "\n")
    
    # Start pylsp process
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pylsp",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Initialize LSP
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": f"file://{Path.cwd()}",
                "capabilities": {}
            }
        }
        
        message = json.dumps(init_request)
        content_length = len(message.encode('utf-8'))
        request = f"Content-Length: {content_length}\r\n\r\n{message}"
        
        process.stdin.write(request.encode('utf-8'))
        await process.stdin.drain()
        
        # Read response
        response_data = await asyncio.wait_for(process.stdout.read(1024), timeout=5.0)
        print(f"Initialize response: {response_data.decode('utf-8', errors='ignore')}")
        
        # Send initialized notification
        initialized = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }
        
        message = json.dumps(initialized)
        content_length = len(message.encode('utf-8'))
        request = f"Content-Length: {content_length}\r\n\r\n{message}"
        
        process.stdin.write(request.encode('utf-8'))
        await process.stdin.drain()
        
        # Send didOpen notification
        did_open = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": f"file://{test_file}",
                    "languageId": "python",
                    "version": 1,
                    "text": content
                }
            }
        }
        
        message = json.dumps(did_open)
        content_length = len(message.encode('utf-8'))
        request = f"Content-Length: {content_length}\r\n\r\n{message}"
        
        process.stdin.write(request.encode('utf-8'))
        await process.stdin.drain()
        
        print("Sent didOpen notification, waiting for diagnostics...")
        
        # Wait for diagnostics (they come as notifications)
        try:
            while True:
                response_data = await asyncio.wait_for(process.stdout.read(2048), timeout=10.0)
                response_text = response_data.decode('utf-8', errors='ignore')
                print(f"Received: {response_text}")
                
                if "publishDiagnostics" in response_text:
                    print("\n*** DIAGNOSTICS FOUND! ***")
                    break
                    
        except asyncio.TimeoutError:
            print("Timeout waiting for diagnostics")
        
        # Cleanup
        process.terminate()
        await process.wait()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pylsp_directly())