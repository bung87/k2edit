"""
LSP Indexer for K2Edit Agentic System
Handles Language Server Protocol integration for code intelligence
"""

import json
import logging
import asyncio
import subprocess
import threading
import queue
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import uuid


class LSPIndexer:
    """Language Server Protocol indexer for code intelligence"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger("k2edit")
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
                            "pycodestyle": {"enabled": False},
                            "pyflakes": {"enabled": False},
                            "mccabe": {"enabled": False}
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
        
        # Add a small delay to show progress messages
        if progress_callback:
            await progress_callback("Starting symbol indexing...")
            await asyncio.sleep(0.5)
        
        # Detect language and start appropriate server
        language = await self._detect_language()
        if progress_callback:
            await progress_callback(f"Detected language: {language}")
            await asyncio.sleep(0.3)
        
        if language in self.server_configs:
            await self._start_language_server(language)
            if progress_callback:
                await progress_callback(f"Started {language} language server")
                await asyncio.sleep(0.3)
        elif progress_callback:
            await progress_callback(f"No language server configured for {language}")
            
        # Build initial index with progress updates
        await self._build_initial_index(progress_callback)
        
        self.logger.info(f"LSP indexer initialized for {language}")
        if progress_callback:
            await progress_callback("Symbol indexing completed")
        
    async def _detect_language(self) -> str:
        """Detect the primary language of the project"""
        for language, config in self.server_configs.items():
            for ext in config["extensions"]:
                if any(self.project_root.rglob(f"*{ext}")):
                    return language
        return "unknown"
        
    async def _start_language_server(self, language: str):
        """Start the language server for the detected language"""
        if language not in self.server_configs:
            return
            
        config = self.server_configs[language]
        
        try:
            # Start language server process
            process = subprocess.Popen(
                config["command"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_root)
            )
            
            self.language_servers[language] = {
                "process": process,
                "config": config,
                "message_id": 0,
                "response_queue": queue.Queue()
            }
            
            # Initialize LSP connection
            await self._initialize_lsp_connection(language)
            
        except Exception as e:
            self.logger.error(f"Failed to start {language} language server: {e}")
            
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
                        "completion": {"dynamicRegistration": True}
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
            process.stdin.flush()
            
        except Exception as e:
            self.logger.error(f"Failed to send LSP message: {e}")
            
    async def _build_initial_index(self, progress_callback=None):
        """Build initial symbol index for all files with progress updates"""
        language = await self._detect_language()
        if language == "unknown":
            self.logger.info("Unknown language detected, skipping initial indexing")
            if progress_callback:
                await progress_callback("Unknown language detected, skipping indexing")
            return
            
        # Find all relevant files
        extensions = self.server_configs[language]["extensions"]
        files = []
        for ext in extensions:
            files.extend(self.project_root.rglob(f"*{ext}"))
            
        self.logger.info(f"Starting initial symbol indexing for {language} project")
        self.logger.info(f"Found {len(files)} files to index with extensions: {extensions}")
        
        if progress_callback:
            await progress_callback(f"Found {len(files)} files to index")
        
        # Index each file with progress logging
        indexed_count = 0
        failed_count = 0
        
        for i, file_path in enumerate(files):
            try:
                await self._index_file(file_path, language)
                indexed_count += 1
                
                # Report progress
                progress = (i + 1) / len(files) * 100
                if progress_callback and (i + 1) % 5 == 0:  # Update every 5 files
                    await progress_callback(f"Indexing symbols... {i + 1}/{len(files)} files ({progress:.1f}%)")
                
                # Log progress every 10 files
                if indexed_count % 10 == 0:
                    self.logger.info(f"Indexed {indexed_count}/{len(files)} files...")
                    
            except Exception as e:
                failed_count += 1
                self.logger.warning(f"Failed to index {file_path}: {e}")
                
        self.logger.info(f"Initial indexing complete: {indexed_count} successful, {failed_count} failed")
        if progress_callback:
            await progress_callback(f"Indexing complete: {indexed_count} files indexed, {failed_count} failed")
            
    async def _index_file(self, file_path: Path, language: str):
        """Index a single file for symbols"""
        try:
            relative_path = file_path.relative_to(self.project_root)
            
            self.logger.debug(f"Indexing symbols for file: {relative_path}")
            
            # Request document symbols
            symbols = await self._get_document_symbols(str(relative_path), language)
            
            # Count symbol types for this file
            symbol_types = {}
            for symbol in symbols:
                symbol_type = symbol.get("kind", "unknown")
                symbol_types[symbol_type] = symbol_types.get(symbol_type, 0) + 1
            
            self.logger.debug(f"Found {len(symbols)} symbols in {relative_path}: {symbol_types}")
            
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
            self.logger.error(f"Failed to index file {file_path}: {e}")
            
    async def _get_document_symbols(self, file_path: str, language: str) -> List[Dict[str, Any]]:
        """Get symbols from a specific file via LSP"""
        if language not in self.language_servers:
            return []
            
        server_info = self.language_servers[language]
        
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
            response = await self._send_lsp_request(language, request)
            server_info["message_id"] += 1
            
            if response and "result" in response:
                self.logger.debug(f"LSP response for {file_path}: {response}")
                result = response["result"]
                if isinstance(result, list):
                    return self._parse_lsp_symbols(result)
                else:
                    self.logger.debug(f"Unexpected LSP result format: {type(result)} - {result}")
                    return []
        except Exception as e:
            self.logger.error(f"LSP request failed for {file_path}: {e}")
            
        # Fallback: parse basic symbols using regex if LSP not available
        file_path_obj = self.project_root / file_path
        if file_path_obj.exists():
            symbols = await self._parse_basic_symbols(file_path_obj)
            
        return symbols
        
    async def _send_lsp_request(self, language: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send LSP request and wait for response"""
        if language not in self.language_servers:
            return None
            
        server_info = self.language_servers[language]
        process = server_info["process"]
        
        try:
            # Send the request
            message_str = json.dumps(request)
            content_length = len(message_str.encode('utf-8'))
            header = f"Content-Length: {content_length}\r\n\r\n"
            
            process.stdin.write((header + message_str).encode('utf-8'))
            process.stdin.flush()
            
            # Read response
            return await self._read_lsp_response(process)
            
        except Exception as e:
            self.logger.error(f"Failed to send LSP request: {e}")
            return None
            
    async def _read_lsp_response(self, process: subprocess.Popen) -> Optional[Dict[str, Any]]:
        """Read response from LSP server"""
        try:
            # Read headers
            headers = {}
            while True:
                line = process.stdout.readline().decode('utf-8').strip()
                if not line:
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Read content
            if 'Content-Length' in headers:
                content_length = int(headers['Content-Length'])
                content = process.stdout.read(content_length).decode('utf-8')
                return json.loads(content)
                
        except Exception as e:
            self.logger.error(f"Failed to read LSP response: {e}")
            return None
            
    def _parse_lsp_symbols(self, lsp_symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
                    "start_line": start_line,
                    "end_line": end_line,
                    "parent": parent,
                    "detail": symbol.get("detail", ""),
                    "children": []
                }

                symbols.append(symbol_data)

                # Handle nested symbols
                children = symbol.get("children", [])
                for child in children:
                    parse_symbol(child, name)
                    
            except Exception as e:
                self.logger.debug(f"Skipping malformed symbol: {symbol} - {e}")
                return

        # Handle both list and dict formats
        if isinstance(lsp_symbols, list):
            for symbol in lsp_symbols:
                parse_symbol(symbol)
        elif isinstance(lsp_symbols, dict):
            parse_symbol(lsp_symbols)

        return symbols
        
    async def _parse_basic_symbols(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse basic symbols using regex as fallback"""
        symbols = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines()
            
            # Language-specific parsing
            if file_path.suffix == '.py':
                symbols = await self._parse_python_symbols(lines)
            elif file_path.suffix in ['.js', '.ts']:
                symbols = await self._parse_javascript_symbols(lines)
            elif file_path.suffix == '.nim':
                symbols = await self._parse_nim_symbols(lines)
                
        except Exception as e:
            self.logger.error(f"Failed to parse symbols from {file_path}: {e}")
            
        return symbols
        
    async def _parse_python_symbols(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse Python symbols using regex"""
        import re
        symbols = []
        
        class_pattern = re.compile(r'^class\s+(\w+)')
        func_pattern = re.compile(r'^(?:def|async\s+def)\s+(\w+)')
        var_pattern = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*=')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Classes
            match = class_pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": "class",
                    "line": i + 1,
                    "type": "class"
                })
                
            # Functions
            match = func_pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": "function",
                    "line": i + 1,
                    "type": "function"
                })
                
            # Constants
            match = var_pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": "constant",
                    "line": i + 1,
                    "type": "constant"
                })
                
        return symbols
        
    async def _parse_javascript_symbols(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse JavaScript/TypeScript symbols"""
        import re
        symbols = []
        
        class_pattern = re.compile(r'^(?:export\s+)?(?:class|interface)\s+(\w+)')
        func_pattern = re.compile(r'^(?:export\s+)?(?:function|const\s+\w+\s*=\s*(?:async\s+)?(?:\([^)]*\)\s*=>|function))')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Classes and interfaces
            match = class_pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": "class",
                    "line": i + 1,
                    "type": "class"
                })
                
        return symbols
        
    async def _parse_nim_symbols(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse Nim symbols"""
        import re
        symbols = []
        
        type_pattern = re.compile(r'^type\s+(\w+)')
        proc_pattern = re.compile(r'^(?:proc|func|method)\s+(\w+)')
        const_pattern = re.compile(r'^const\s+(\w+)')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Types
            match = type_pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": "type",
                    "line": i + 1,
                    "type": "type"
                })
                
            # Procedures
            match = proc_pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": "function",
                    "line": i + 1,
                    "type": "function"
                })
                
            # Constants
            match = const_pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": "constant",
                    "line": i + 1,
                    "type": "constant"
                })
                
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
            self.logger.warning(f"Failed to parse Python imports from {file_path}: {e}")
            
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
            self.logger.warning(f"Failed to parse JavaScript imports from {file_path}: {e}")
            
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
            self.logger.warning(f"Failed to parse Nim imports from {file_path}: {e}")
            
        return imports
        
    async def get_project_symbols(self) -> List[Dict[str, Any]]:
        """Get all symbols across the project"""
        self.logger.info("Starting project-wide symbol fetching...")
        
        all_symbols = []
        total_files = len(self.symbol_index)
        total_symbols_count = 0
        
        # Log indexing status
        self.logger.info(f"Symbol index contains {total_files} files")
        
        # Count symbols by type for detailed logging
        symbol_type_counts = {}
        
        for file_path, symbols in self.symbol_index.items():
            file_symbol_count = len(symbols)
            total_symbols_count += file_symbol_count
            
            # Track symbol types
            for symbol in symbols:
                symbol_type = symbol.get("kind", "unknown")
                symbol_type_counts[symbol_type] = symbol_type_counts.get(symbol_type, 0) + 1
                
                symbol["file_path"] = file_path
                all_symbols.append(symbol)
        
        # Log detailed summary
        self.logger.info(f"Fetched {total_symbols_count} total symbols from {total_files} files")
        self.logger.info(f"Symbol type breakdown: {symbol_type_counts}")
        
        # Log top files by symbol count
        file_symbol_counts = [(fp, len(syms)) for fp, syms in self.symbol_index.items()]
        file_symbol_counts.sort(key=lambda x: x[1], reverse=True)
        
        if file_symbol_counts:
            self.logger.info("Top 5 files by symbol count:")
            for file_path, count in file_symbol_counts[:5]:
                self.logger.info(f"  - {file_path}: {count} symbols")
        
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
        
    async def get_enhanced_context_for_file(self, file_path: str, line: int = None) -> Dict[str, Any]:
        """Get enhanced context for a file including LSP outline"""
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
        language = await self._detect_language()
        
        if file_path:
            # Refresh specific file
            await self._index_file(Path(file_path), language)
        else:
            # Refresh entire project
            await self._build_initial_index()
            
    def shutdown(self):
        """Shutdown all language servers"""
        for language, server_info in self.language_servers.items():
            try:
                if "process" in server_info:
                    server_info["process"].terminate()
                    server_info["process"].wait()
            except Exception as e:
                self.logger.error(f"Error shutting down {language} server: {e}")
                
        self.language_servers.clear()