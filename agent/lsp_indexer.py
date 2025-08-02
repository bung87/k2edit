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
        self.logger = logger or logging.getLogger(__name__)
        self.project_root = None
        self.language_servers = {}
        self.symbol_index = {}
        self.file_index = {}
        self.diagnostics = {}
        
        # Language server configurations
        self.server_configs = {
            "python": {
                "command": ["pylsp"],
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
        
    async def initialize(self, project_root: str):
        """Initialize LSP indexer for project"""
        self.project_root = Path(project_root)
        
        # Detect language and start appropriate server
        language = await self._detect_language()
        if language in self.server_configs:
            await self._start_language_server(language)
            
        # Build initial index
        await self._build_initial_index()
        
        self.logger.info(f"LSP indexer initialized for {language}")
        
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
            
    async def _build_initial_index(self):
        """Build initial symbol index for all files"""
        language = await self._detect_language()
        if language == "unknown":
            return
            
        # Find all relevant files
        extensions = self.server_configs[language]["extensions"]
        files = []
        for ext in extensions:
            files.extend(self.project_root.rglob(f"*{ext}"))
            
        # Index each file
        for file_path in files:
            await self._index_file(file_path, language)
            
    async def _index_file(self, file_path: Path, language: str):
        """Index a single file for symbols"""
        try:
            relative_path = file_path.relative_to(self.project_root)
            
            # Request document symbols
            symbols = await self._get_document_symbols(str(relative_path), language)
            
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
        """Get symbols from a specific file"""
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
        
        # This would normally wait for response, simplified for demo
        symbols = []
        
        # Fallback: parse basic symbols using regex if LSP not available
        file_path_obj = self.project_root / file_path
        if file_path_obj.exists():
            symbols = await self._parse_basic_symbols(file_path_obj)
            
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
                
        except Exception:
            pass
            
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
                
        except Exception:
            pass
            
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
                
        except Exception:
            pass
            
        return imports
        
    async def get_project_symbols(self) -> List[Dict[str, Any]]:
        """Get all symbols across the project"""
        all_symbols = []
        
        for file_path, symbols in self.symbol_index.items():
            for symbol in symbols:
                symbol["file_path"] = file_path
                all_symbols.append(symbol)
                
        return all_symbols
        
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