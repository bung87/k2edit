"""
LSP Indexer for K2Edit Agentic System
Handles Language Server Protocol integration for code intelligence
"""

import json
from aiologger import Logger
from aiologger.levels import LogLevel
import asyncio
import subprocess
import threading
import queue
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import uuid


class LSPIndexer:
    """Language Server Protocol indexer for code intelligence"""
    
    def __init__(self, logger: Logger = None):
        self.logger = logger or Logger(name="k2edit")
        self.project_root = None
        self.language_servers = {}
        self.symbol_index = {}
        self.file_index = {}
        self.diagnostics = {}
        
        # Language server configurations
        self.server_configs = {
            "python": {
                "command": ["/Users/bung/Library/Python/3.9/bin/pylsp"],
                "extensions": [".py"],
                "settings": {
                    "pylsp": {
                        "plugins": {
                            "pycodestyle": {"enabled": True},
                            "pyflakes": {"enabled": True},
                            "mccabe": {"enabled": True}
                        }
                    }
                }
            },
            "javascript": {
                "command": ["typescript-language-server", "--stdio"],
                "extensions": [".js", ".ts", ".jsx", ".tsx"],
                "settings": {}
            },
            "typescript": {
                "command": ["typescript-language-server", "--stdio"],
                "extensions": [".ts", ".tsx"],
                "settings": {}
            },
            "go": {
                "command": ["gopls"],
                "extensions": [".go"],
                "settings": {}
            },
            "rust": {
                "command": ["rust-analyzer"],
                "extensions": [".rs"],
                "settings": {}
            },
            "nim": {
                "command": ["nimlsp"],
                "extensions": [".nim"],
                "settings": {}
            }
        }
        
    async def initialize(self, project_root: str, progress_callback=None):
        """Initialize LSP indexer for project with optional progress callback"""
        self.project_root = Path(project_root)
        await self.logger.info(f"Initializing LSP indexer for project: {self.project_root}")
        
        # Add a small delay to show progress messages
        if progress_callback:
            await progress_callback("Starting symbol indexing...")
            await asyncio.sleep(0.1)  # Reduced delay
        
        # Detect language and start appropriate server
        language = await self._detect_language()
        await self.logger.info(f"Detected language: {language}")
        if progress_callback:
            await progress_callback(f"Detected language: {language}")
            await asyncio.sleep(0.1)  # Reduced delay
        
        if language in self.server_configs:
            await self.logger.info(f"Starting language server for {language}...")
            await self._start_language_server(language)
            if progress_callback:
                await progress_callback(f"Started {language} language server")
                await asyncio.sleep(0.1)  # Reduced delay
        else:
            await self.logger.warning(f"No language server configured for {language}")
            if progress_callback:
                await progress_callback(f"No language server configured for {language}")
            
        # Build initial index in background (non-blocking)
        asyncio.create_task(self._build_initial_index_background(progress_callback))
        
        await self.logger.info(f"LSP indexer initialized for {language}")
        if progress_callback:
            await progress_callback("Symbol indexing started in background...")
            
    async def force_diagnostics_for_file(self, file_path: str):
        """Force LSP server to analyze a specific file and provide diagnostics"""
        try:
            language = await self._detect_file_language(file_path)
            if language == "unknown" or language not in self.language_servers:
                await self.logger.warning(f"Cannot force diagnostics: language {language} not supported")
                return
                
            await self.logger.info(f"Forcing diagnostics for file: {file_path}")
            await self._notify_file_opened(file_path)
            
            # Small delay to allow LSP server to process
            await asyncio.sleep(1)
            
            # Re-request diagnostics
            relative_path = str(Path(file_path).relative_to(self.project_root))
            diagnostics = self.diagnostics.get(relative_path, [])
            await self.logger.info(f"Retrieved {len(diagnostics)} diagnostics for {file_path}")
            
        except Exception as e:
            await self.logger.error(f"Error forcing diagnostics: {e}")
    
    async def _detect_language(self) -> str:
        """Detect the primary language of the project"""
        for language, config in self.server_configs.items():
            for ext in config["extensions"]:
                if any(self.project_root.rglob(f"*{ext}")):
                    return language
        return "unknown"
    
    async def _detect_file_language(self, file_path: str) -> str:
        """Detect the language of a specific file based on extension"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        for language, config in self.server_configs.items():
            if extension in config["extensions"]:
                return language
        return "unknown"
    
    def _should_skip_python_file(self, file_path: Path) -> bool:
        """Check if a Python file should be skipped (e.g., in virtual environment)"""
        try:
            # Convert to absolute path for reliable comparison
            abs_path = file_path.resolve()
            project_root = self.project_root.resolve()
            
            # Check if file is within the project root
            if not abs_path.is_relative_to(project_root):
                return True
            
            # Common virtual environment directory patterns
            venv_patterns = [
                "venv/",
                "env/",
                ".venv/",
                ".env/",
                "virtualenv/",
                "__pycache__/",
                ".pytest_cache/",
                ".mypy_cache/",
                ".coverage",
                "site-packages/",
                "dist-packages/",
                "lib/python",
                "lib64/python",
                "include/python",
                "Scripts/",  # Windows virtual environments
                "bin/",      # Unix virtual environments
            ]
            
            # Check if any part of the path matches virtual environment patterns
            path_str = str(abs_path)
            for pattern in venv_patterns:
                if pattern in path_str:
                    return True
            
            # Check for common Python package directories that should be skipped
            skip_dirs = {
                "node_modules",  # Sometimes present in Python projects
                ".git",
                ".hg",
                ".svn",
                ".tox",
                ".eggs",
                "build",
                "dist",
                "*.egg-info",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".coverage",
                ".cache",
                ".local",
                ".virtualenvs",
            }
            
            # Check each directory in the path
            for part in abs_path.parts:
                if part in skip_dirs:
                    return True
                # Check for egg-info patterns
                if part.endswith('.egg-info'):
                    return True
            
            # Additional check for site-packages in the path
            path_parts = abs_path.parts
            for i, part in enumerate(path_parts):
                if part in ['site-packages', 'dist-packages']:
                    return True
                # Check for lib/pythonX.Y/site-packages pattern
                if i > 0 and part.startswith('python') and path_parts[i-1] in ['lib', 'lib64']:
                    return True
            
            return False
            
        except Exception as e:
            # If there's any error in checking, log it but don't skip the file
            # This ensures we don't accidentally skip important files
            return False
    
    async def _log_python_filtering_stats(self):
        """Log statistics about Python file filtering for debugging"""
        try:
            # Count files that would be filtered out
            extensions = self.server_configs["python"]["extensions"]
            total_python_files = 0
            filtered_files = 0
            
            for ext in extensions:
                all_files = list(self.project_root.rglob(f"*{ext}"))
                total_python_files += len(all_files)
                
                for file_path in all_files:
                    if self._should_skip_python_file(file_path):
                        filtered_files += 1
            
            if total_python_files > 0:
                filter_percentage = (filtered_files / total_python_files) * 100
                await self.logger.info(f"Python file filtering stats: {filtered_files}/{total_python_files} files would be filtered ({filter_percentage:.1f}%)")
                
        except Exception as e:
            await self.logger.debug(f"Could not generate Python filtering stats: {e}")
    
    async def _start_language_server(self, language: str):
        """Start the language server for the detected language"""
        if language not in self.server_configs:
            await self.logger.error(f"Cannot start language server: no configuration for {language}")
            return

        config = self.server_configs[language]
        await self.logger.info(f"Starting {language} language server with command: {' '.join(config['command'])}")

        try:
            # Start language server process using asyncio
            process = await asyncio.create_subprocess_exec(
                *config["command"],
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )

            self.language_servers[language] = {
                "process": process,
                "config": config,
                "message_id": 0,
                "response_queue": asyncio.Queue(),
                "reader_lock": asyncio.Lock()  # Add lock for synchronized reading
            }

            await self.logger.info(f"{language} language server started with PID: {process.pid}")

            # Create a task to log stderr
            asyncio.create_task(self._log_stderr(language, process.stderr))

            # Initialize LSP connection
            await self._initialize_lsp_connection(language)

            # Start single reader task for all LSP messages
            asyncio.create_task(self._read_lsp_messages(language))

        except Exception as e:
            await self.logger.error(f"Failed to start {language} language server: {e}", exc_info=True)

    async def _log_stderr(self, language: str, stderr):
        """Log stderr from language server process."""
        while not stderr.at_eof():
            line = await stderr.readline()
            if line:
                await self.logger.error(f"[{language}-lsp-stderr] {line.decode().strip()}")
            
    async def _initialize_lsp_connection(self, language: str):
        """Initialize LSP connection with capabilities"""
        if language not in self.language_servers:
            return
            
        server_info = self.language_servers[language]
        
        # Initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": server_info["message_id"],
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": f"file://{self.project_root}",
                "capabilities": {
                    "textDocument": {
                        "hover": {"dynamicRegistration": True},
                        "definition": {"dynamicRegistration": True},
                        "references": {"dynamicRegistration": True},
                        "documentSymbol": {"dynamicRegistration": True},
                        "workspaceSymbol": {"dynamicRegistration": True},
                        "completion": {"dynamicRegistration": True},
                        "publishDiagnostics": {"relatedInformation": True}
                    },
                    "workspace": {
                        "symbol": {"dynamicRegistration": True},
                        "workspaceFolders": True
                    }
                }
            }
        }
        
        await self._send_lsp_message(language, init_request)
        server_info["message_id"] += 1
        
    async def _send_lsp_message(self, language: str, message: Dict[str, Any]):
        """Send message to language server"""
        if language not in self.language_servers:
            return
            
        server_info = self.language_servers[language]
        process = server_info["process"]
        
        try:
            message_str = json.dumps(message)
            content_length = len(message_str.encode('utf-8'))
            
            # LSP protocol format
            header = f"Content-Length: {content_length}\r\n\r\n"
            process.stdin.write((header + message_str).encode('utf-8'))
            await process.stdin.drain()
            
        except Exception as e:
            await self.logger.error(f"Failed to send LSP message: {e}")
            
    async def _build_initial_index_background(self, progress_callback=None):
        """Build initial symbol index for all files in background with progress updates"""
        language = await self._detect_language()
        if language == "unknown":
            await self.logger.info("Unknown language detected, skipping initial indexing")
            if progress_callback:
                await progress_callback("Unknown language detected, skipping indexing")
            return
            
        # Find all relevant files
        extensions = self.server_configs[language]["extensions"]
        files = []
        for ext in extensions:
            all_files = list(self.project_root.rglob(f"*{ext}"))
            
            # Special handling for Python projects - filter out virtual environment directories
            if language == "python":
                filtered_files = []
                skipped_count = 0
                for file_path in all_files:
                    # Check if file is in a virtual environment directory
                    if self._should_skip_python_file(file_path):
                        skipped_count += 1
                        continue
                    filtered_files.append(file_path)
                files.extend(filtered_files)
                
                if skipped_count > 0:
                    await self.logger.info(f"Filtered out {skipped_count} virtual environment files for Python project")
            else:
                files.extend(all_files)
            
        await self.logger.info(f"Starting initial symbol indexing for {language} project")
        await self.logger.info(f"Found {len(files)} files to index with extensions: {extensions}")
        
        if progress_callback:
            await progress_callback(f"Found {len(files)} files to index")
        
        # Index each file with progress logging
        indexed_count = 0
        failed_count = 0
        
        for i, file_path in enumerate(files):
            try:
                await self._index_file(file_path, language)
                
                # Also notify LSP server about this file to trigger diagnostics
                await self._notify_file_opened(str(file_path.absolute()))
                
                indexed_count += 1
                
                # Report progress less frequently to reduce overhead
                progress = (i + 1) / len(files) * 100
                if progress_callback and (i + 1) % 10 == 0:  # Update every 10 files instead of 5
                    await progress_callback(f"Indexing symbols... {i + 1}/{len(files)} files ({progress:.1f}%)")
                
                # Log progress every 20 files instead of 10
                if indexed_count % 20 == 0:
                    await self.logger.info(f"Indexed {indexed_count}/{len(files)} files...")
                    
            except Exception as e:
                failed_count += 1
                await self.logger.warning(f"Failed to index {file_path}: {e}")
                
        await self.logger.info(f"Initial indexing complete: {indexed_count} successful, {failed_count} failed")
        if progress_callback:
            await progress_callback(f"Indexing complete: {indexed_count} files indexed, {failed_count} failed")
            
    async def _index_file(self, file_path: Path, language: str):
        """Index a single file for symbols"""
        try:
            relative_path = file_path.relative_to(self.project_root)
            
            await self.logger.debug(f"Indexing symbols for file: {relative_path}")
            
            # Request document symbols
            symbols = await self._get_document_symbols(str(relative_path), language)
            
            # Count symbol types for this file
            symbol_types = {}
            for symbol in symbols:
                symbol_type = symbol.get("kind", "unknown")
                symbol_types[symbol_type] = symbol_types.get(symbol_type, 0) + 1
            
            await self.logger.debug(f"Found {len(symbols)} symbols in {relative_path}: {symbol_types}")
            
            # Store in index
            self.symbol_index[str(relative_path)] = symbols
            
            # Store file metadata
            self.file_index[str(relative_path)] = {
                "language": language,
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime,
                "symbols": len(symbols)
            }
            
        except Exception as e:
            await self.logger.error(f"Failed to index file {file_path}: {e}")
            
    async def _get_document_symbols(self, file_path: str, language: str) -> List[Dict[str, Any]]:
        """Get symbols from a specific file via LSP"""
        # Ensure the correct language server for this file is running
        file_language = await self._detect_file_language(file_path)
        if file_language == "unknown":
            file_language = language
            
        if file_language not in self.language_servers:
            await self._start_language_server(file_language)
            
        if file_language not in self.language_servers:
            # No fallback parsing available
            return []
            
        server_info = self.language_servers[file_language]
        
        # Request document symbols
        request = {
            "jsonrpc": "2.0",
            "id": server_info["message_id"],
            "method": "textDocument/documentSymbol",
            "params": {
                "textDocument": {
                    "uri": f"file://{self.project_root}/{file_path}"
                }
            }
        }
        
        try:
            # Send request and wait for response
            response = await self._send_lsp_request(file_language, request)
            server_info["message_id"] += 1
            
            if response and "result" in response:
                await self.logger.debug(f"LSP response for {file_path}")
                result = response["result"]
                if isinstance(result, list):
                    return await self._parse_lsp_symbols(result)
                else:
                    await self.logger.debug(f"Unexpected LSP result format: {type(result)} - {result}")
                    return []
        except Exception as e:
            await self.logger.error(f"LSP request failed for {file_path}: {e}")
            
        # No fallback parsing - return empty list if LSP not available
        return []
        
    async def _send_lsp_request(self, language: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send LSP request and wait for response"""
        if language not in self.language_servers:
            return None
            
        server_info = self.language_servers[language]
        process = server_info["process"]
        message_id = request.get("id", server_info["message_id"])
        
        try:
            # Send the request
            message_str = json.dumps(request)
            content_length = len(message_str.encode('utf-8'))
            header = f"Content-Length: {content_length}\r\n\r\n"
            
            process.stdin.write((header + message_str).encode('utf-8'))
            await process.stdin.drain()
            
            # Read response using the new queue-based method
            response = await self._read_lsp_response(language, message_id)
            
            # Increment message ID for next request
            if request.get("id") == server_info["message_id"]:
                server_info["message_id"] += 1
                
            return response
            
        except Exception as e:
            await self.logger.error(f"Failed to send LSP request: {e}")
            return None

    async def _read_lsp_messages(self, language: str):
        """Read all LSP messages (responses and notifications) from the language server"""
        if language not in self.language_servers:
            return
            
        server_info = self.language_servers[language]
        process = server_info["process"]
        reader_lock = server_info["reader_lock"]
        
        await self.logger.info(f"Started reading LSP messages from {language} language server")
        
        while True:
            try:
                async with reader_lock:
                    # Read headers
                    headers = {}
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            await self.logger.info(f"LSP process stdout closed for {language}")
                            return
                        line = line.decode('utf-8').strip()
                        if not line:
                            break
                        if ':' in line:
                            key, value = line.split(':', 1)
                            headers[key.strip()] = value.strip()
                    
                    # Read content
                    if 'Content-Length' in headers:
                        content_length = int(headers['Content-Length'])
                        content = await process.stdout.read(content_length)
                        response = json.loads(content.decode('utf-8'))
                        
                        # Handle notifications vs responses
                        if "method" in response:
                            # This is a notification (like diagnostics)
                            await self._handle_lsp_notification(language, response)
                        else:
                            # This is a response to a request
                            await server_info["response_queue"].put(response)
                            
            except asyncio.CancelledError:
                await self.logger.info(f"LSP message reader cancelled for {language}")
                break
            except Exception as e:
                await self.logger.error(f"Error reading LSP messages for {language}: {e}")
                break
                
        await self.logger.info(f"Stopped reading LSP messages from {language} language server")
            
    async def _read_lsp_response(self, language: str, message_id: int) -> Optional[Dict[str, Any]]:
        """Read response from LSP server using response queue"""
        if language not in self.language_servers:
            return None
            
        server_info = self.language_servers[language]
        response_queue = server_info["response_queue"]
        
        try:
            # Wait for response with timeout
            timeout = 10  # 10 seconds timeout
            while True:
                try:
                    response = await asyncio.wait_for(response_queue.get(), timeout=timeout)
                    
                    # Check if this response matches our request ID
                    if response.get("id") == message_id:
                        return response
                    else:
                        # Put it back in the queue if it's not for us
                        await response_queue.put(response)
                        await asyncio.sleep(0.01)  # Small delay to avoid busy waiting
                        
                except asyncio.TimeoutError:
                    await self.logger.error(f"Timeout waiting for LSP response {message_id}")
                    return None
                    
        except Exception as e:
            await self.logger.error(f"Failed to read LSP response: {e}")
            return None
            
    async def _parse_lsp_symbols(self, lsp_symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse LSP symbols into our format"""
        symbols = []

        def parse_symbol(symbol: Dict[str, Any], parent: str = None):
            kind_map = {
                1: "file", 2: "module", 3: "namespace", 4: "package",
                5: "class", 6: "method", 7: "property", 8: "field",
                9: "constructor", 10: "enum", 11: "interface", 12: "function",
                13: "variable", 14: "constant", 15: "string", 16: "number",
                17: "boolean", 18: "array", 19: "object", 20: "key",
                21: "null", 22: "enum_member", 23: "struct", 24: "event",
                25: "operator", 26: "type_parameter"
            }

            try:
                # Handle different symbol formats
                if isinstance(symbol, str):
                    # Skip string entries
                    return
                
                name = symbol.get("name", "")
                kind = kind_map.get(symbol.get("kind", 0), "unknown")
                
                # Handle different location formats
                location = symbol.get("location", symbol)
                range_info = location.get("range", symbol)
                
                start_line = range_info.get("start", {}).get("line", 0) + 1
                end_line = range_info.get("end", {}).get("line", 0) + 1

                symbol_data = {
                    "name": name,
                    "kind": kind,
                    "type": kind,
                    "parent": parent,
                    "children": []
                }

                symbols.append(symbol_data)

                # Handle nested symbols
                children = symbol.get("children", [])
                for child in children:
                    parse_symbol(child, name)
                    
            except Exception as e:
                # Log will be handled at async level
                pass

        # Handle both list and dict formats
        try:
            if isinstance(lsp_symbols, list):
                for symbol in lsp_symbols:
                    parse_symbol(symbol)
            elif isinstance(lsp_symbols, dict):
                parse_symbol(lsp_symbols)
        except Exception as e:
            await self.logger.debug(f"Skipping malformed symbols: {e}")

        return symbols
        
    async def get_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """Get symbols for a specific file"""
        relative_path = str(Path(file_path).relative_to(self.project_root))
        return self.symbol_index.get(relative_path, [])
        
        
    async def get_dependencies(self, file_path: str) -> List[str]:
        """Get dependencies for a specific file"""
        # This would use LSP to find imports/includes
        # For now, return basic imports based on file extension
        
        file_path_obj = Path(file_path)
        
        if file_path_obj.suffix == '.py':
            return await self._get_python_imports(file_path_obj)
        elif file_path_obj.suffix in ['.js', '.ts']:
            return await self._get_javascript_imports(file_path_obj)
        elif file_path_obj.suffix == '.nim':
            return await self._get_nim_imports(file_path_obj)
            
        return []
        
    async def _get_python_imports(self, file_path: Path) -> List[str]:
        """Get Python imports"""
        imports = []
        try:
            content = file_path.read_text()
            import re
            
            # Basic import patterns
            patterns = [
                r'^import\s+([\w.]+)',
                r'^from\s+([\w.]+)\s+import',
                r'^import\s+([\w.]+)\s+as'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
                
        except Exception as e:
            await self.logger.warning(f"Failed to parse Python imports from {file_path}: {e}")
            
        return imports
        
    async def _get_javascript_imports(self, file_path: Path) -> List[str]:
        """Get JavaScript/TypeScript imports"""
        imports = []
        try:
            content = file_path.read_text()
            import re
            
            # Basic import patterns
            patterns = [
                r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
                r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                r'import\s+[\'"]([^\'"]+)[\'"]'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                imports.extend(matches)
                
        except Exception as e:
            await self.logger.warning(f"Failed to parse JavaScript imports from {file_path}: {e}")
            
        return imports
        
    async def _get_nim_imports(self, file_path: Path) -> List[str]:
        """Get Nim imports"""
        imports = []
        try:
            content = file_path.read_text()
            import re
            
            # Basic import patterns for Nim
            patterns = [
                r'^import\s+([\w/]+)',
                r'^from\s+([\w/]+)\s+import',
                r'^include\s+([\w/]+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
                
        except Exception as e:
            await self.logger.warning(f"Failed to parse Nim imports from {file_path}: {e}")
            
        return imports
        
    async def get_project_symbols(self, top_level_only: bool = False) -> List[Dict[str, Any]]:
        """Get symbols across the project, optionally filtering for top-level symbols only"""
        await self.logger.info(f"Starting project-wide symbol fetching (top_level_only={top_level_only})...")
        
        all_symbols = []
        total_files = len(self.symbol_index)
        total_symbols_count = 0
        
        # Log indexing status
        await self.logger.info(f"Symbol index contains {total_files} files")
        
        # For Python projects, log virtual environment filtering info
        if await self._detect_language() == "python":
            await self._log_python_filtering_stats()
        
        # Count symbols by type for detailed logging
        symbol_type_counts = {}
        
        for file_path, symbols in self.symbol_index.items():
            file_symbol_count = 0
            
            # Track symbol types
            for symbol in symbols:
                # Filter for top-level symbols only if requested
                if top_level_only and symbol.get("parent"):
                    continue
                    
                symbol_type = symbol.get("kind", "unknown")
                symbol_type_counts[symbol_type] = symbol_type_counts.get(symbol_type, 0) + 1
                
                symbol["file_path"] = file_path
                all_symbols.append(symbol)
                file_symbol_count += 1
            
            total_symbols_count += file_symbol_count
        
        # Log detailed summary
        await self.logger.info(f"Fetched {total_symbols_count} total symbols from {total_files} files")
        await self.logger.info(f"Symbol type breakdown: {symbol_type_counts}")
        
        # Log top files by symbol count
        file_symbol_counts = [(fp, len(syms)) for fp, syms in self.symbol_index.items()]
        file_symbol_counts.sort(key=lambda x: x[1], reverse=True)
        
        if file_symbol_counts:
            await self.logger.info("Top 5 files by symbol count:")
            for file_path, count in file_symbol_counts[:5]:
                await self.logger.info(f"  - {file_path}: {count} symbols")
        
        return all_symbols
        
    async def get_document_outline(self, file_path: str) -> Dict[str, Any]:
        """Get structured outline for a document via LSP"""
        language = await self._detect_language()
        if language == "unknown":
            return {"outline": [], "error": "Unsupported language"}
            
        relative_path = str(Path(file_path).relative_to(self.project_root))
        symbols = await self._get_document_symbols(relative_path, language)
        
        # Build hierarchical outline
        outline = self._build_hierarchical_outline(symbols)
        
        return {
            "file_path": relative_path,
            "language": language,
            "outline": outline,
            "symbol_count": len(symbols),
            "classes": [s for s in symbols if s.get("kind") == "class"],
            "functions": [s for s in symbols if s.get("kind") in ["function", "method"]],
            "variables": [s for s in symbols if s.get("kind") in ["variable", "constant", "property"]]
        }
        
    def _build_hierarchical_outline(self, symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build hierarchical outline from flat symbol list"""
        outline = []
        symbol_map = {s["name"]: s for s in symbols}
        
        # Build hierarchy
        for symbol in symbols:
            if not symbol.get("parent"):
                # Top-level symbol
                outline.append(self._build_symbol_tree(symbol, symbols))
                
        return outline
        
    def _build_symbol_tree(self, symbol: Dict[str, Any], all_symbols: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build symbol tree with nested children"""
        tree = symbol.copy()
        tree["children"] = []
        
        # Find children (symbols with this symbol as parent)
        for child in all_symbols:
            if child.get("parent") == symbol["name"]:
                tree["children"].append(self._build_symbol_tree(child, all_symbols))
                
        return tree
        
    async def _notify_file_opened(self, file_path: str):
        """Notify LSP server that a file has been opened to trigger diagnostics"""
        try:
            language = await self._detect_file_language(file_path)
            if language == "unknown" or language not in self.language_servers:
                await self.logger.debug(f"Skipping LSP notification: language {language} not supported")
                return
                
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                await self.logger.debug(f"Skipping LSP notification: file {file_path} does not exist")
                return
                
            # Read file content
            try:
                content = file_path_obj.read_text()
            except Exception as e:
                await self.logger.warning(f"Failed to read file content for LSP: {e}")
                return
                
            # Build LSP URI
            uri = f"file://{file_path_obj.absolute()}"
            
            # Send didOpen notification
            did_open_notification = {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language,
                        "version": 1,
                        "text": content
                    }
                }
            }
            
            await self._send_lsp_message(language, did_open_notification)
            await self.logger.info(f"Notified LSP server about opened file: {file_path} (URI: {uri})")
            
            # Request diagnostics explicitly
            await self._request_diagnostics(language, uri)
            
        except Exception as e:
            await self.logger.warning(f"Failed to notify LSP server about opened file: {e}")

    async def _request_diagnostics(self, language: str, uri: str):
        """Explicitly request diagnostics from LSP server
        
        Note: This method uses the standard LSP approach where textDocument/didOpen
        triggers diagnostics via publishDiagnostics notifications. The newer
        textDocument/diagnostic method (LSP 3.17+) is not widely supported yet.
        """
        # The standard LSP approach relies on textDocument/didOpen to trigger diagnostics
        # via publishDiagnostics notifications, which are handled in _handle_lsp_notification
        await self.logger.debug(f"Diagnostics will be provided via publishDiagnostics after didOpen: {uri}")

    async def get_enhanced_context_for_file(self, file_path: str, line: int = None) -> Dict[str, Any]:
        """Get enhanced context for a file including LSP outline"""
        # Ensure appropriate language server is running for this file
        file_language = await self._detect_file_language(file_path)
        if file_language != "unknown" and file_language not in self.language_servers:
            await self._start_language_server(file_language)
        
        # Ensure file is opened with LSP server
        await self._notify_file_opened(file_path)
        
        outline = await self.get_document_outline(file_path)
        
        # Get additional LSP information
        language = await self._detect_language()
        relative_path = str(Path(file_path).relative_to(self.project_root))
        
        context = {
            "file_path": relative_path,
            "language": language,
            "outline": outline["outline"],
            "symbols": outline["outline"],
            "metadata": {
                "total_symbols": outline["symbol_count"],
                "classes": len(outline["classes"]),
                "functions": len(outline["functions"]),
                "variables": len(outline["variables"])
            }
        }
        
        # If line is provided, get symbols at that line
        if line:
            context["line_context"] = self._get_symbols_at_line(outline.get("classes", []) + outline.get("functions", []), line)
            
        return context
        
    def _get_symbols_at_line(self, symbols: List[Dict[str, Any]], line: int) -> List[Dict[str, Any]]:
        """Get symbols that contain the given line"""
        matching_symbols = []
        
        for symbol in symbols:
            start_line = symbol.get("start_line", 0)
            end_line = symbol.get("end_line", 0)
            if start_line <= line <= end_line:
                matching_symbols.append(symbol)
                
        return matching_symbols
        
    async def find_symbol_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find all references to a symbol"""
        references = []
        
        for file_path, symbols in self.symbol_index.items():
            for symbol in symbols:
                if symbol["name"] == symbol_name:
                    references.append({
                        "file_path": file_path,
                        "symbol": symbol,
                        "line": symbol.get("line", 0)
                    })
                    
        return references
        
    async def get_symbol_definition(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Get definition location for a symbol"""
        for file_path, symbols in self.symbol_index.items():
            for symbol in symbols:
                if symbol["name"] == symbol_name:
                    return {
                        "file_path": file_path,
                        "line": symbol.get("line", 0),
                        "kind": symbol.get("kind", "unknown")
                    }
                    
        return None
        
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific file"""
        relative_path = str(Path(file_path).relative_to(self.project_root))
        return self.file_index.get(relative_path)
        
    async def refresh_index(self, file_path: str = None):
        """Refresh the symbol index"""
        if file_path:
            # Refresh specific file - detect its specific language
            file_language = await self._detect_file_language(file_path)
            if file_language != "unknown" and file_language not in self.language_servers:
                await self._start_language_server(file_language)
            await self._index_file(Path(file_path), file_language or await self._detect_language())
        else:
            # Refresh entire project
            language = await self._detect_language()
            await self._build_initial_index()
            
    async def _handle_lsp_notification(self, language: str, notification: Dict[str, Any]):
        """Handle LSP notifications, including diagnostics"""
        try:
            method = notification.get("method")
            await self.logger.debug(f"Received LSP notification: {method}")
            
            if method == "textDocument/publishDiagnostics":
                params = notification.get("params", {})
                uri = params.get("uri")
                diagnostics = params.get("diagnostics", [])
                
                await self.logger.debug(f"publishDiagnostics - URI: {uri}, diagnostics count: {len(diagnostics)}")
                
                if uri:
                    # Convert URI back to file path
                    file_path = uri.replace("file://", "")
                    
                    # Try to get relative path for project files
                    try:
                        file_path = str(Path(file_path).relative_to(self.project_root))
                    except ValueError:
                        # File is outside project root, use absolute path
                        file_path = str(Path(file_path))
                    
                    self.diagnostics[file_path] = diagnostics
                    
                    # Log diagnostic info
                    if diagnostics:
                        await self.logger.info(f"Received {len(diagnostics)} diagnostics for {file_path}")
                        for diag in diagnostics:
                            severity = diag.get("severity", 1)
                            message = diag.get("message", "")
                            line = diag.get("range", {}).get("start", {}).get("line", 0) + 1
                            await self.logger.info(f"  Line {line}: {message} (severity: {severity})")
                    else:
                        await self.logger.debug(f"No diagnostics for {file_path}")
                else:
                    await self.logger.debug("No URI in publishDiagnostics notification")
            else:
                await self.logger.debug(f"Ignoring non-diagnostic notification: {method}")
        except Exception as e:
            await self.logger.error(f"Error handling LSP notification: {e}")
            await self.logger.error(f"Notification details: {notification}")

    async def get_diagnostics(self, file_path: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get diagnostics for a specific file or all files"""
        await self.logger.debug(f"get_diagnostics called with file_path: {file_path}")
        await self.logger.debug(f"Current diagnostics cache: {list(self.diagnostics.keys())}")
        
        if file_path:
            # Ensure we have an absolute path
            abs_path = Path(file_path).resolve()
            try:
                relative_path = str(abs_path.relative_to(self.project_root))
            except ValueError:
                # File is not in project root, use absolute path
                relative_path = str(abs_path)
            
            diagnostics = self.diagnostics.get(relative_path, [])
            await self.logger.debug(f"Diagnostics for {relative_path}: {len(diagnostics)} items")
            return {relative_path: diagnostics}
        
        await self.logger.debug(f"Returning all diagnostics for {len(self.diagnostics)} files")
        for file_path, diags in self.diagnostics.items():
            await self.logger.debug(f"  {file_path}: {len(diags)} diagnostics")
            
        return self.diagnostics



    async def shutdown(self):
        """Shutdown all language servers"""
        for language, server_info in self.language_servers.items():
            try:
                if "process" in server_info and server_info["process"].returncode is None:
                    server_info["process"].terminate()
                    await server_info["process"].wait()
            except Exception as e:
                await self.logger.error(f"Error shutting down {language} server: {e}")
                
        self.language_servers.clear()