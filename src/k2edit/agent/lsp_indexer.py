"""
LSP Indexer for K2Edit Agentic System
High-level orchestrator for LSP-based code intelligence
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiologger import Logger

from .lsp_client import LSPClient
from .language_configs import LanguageConfigs
from .symbol_parser import SymbolParser
from .file_filter import FileFilter


class LSPIndexer:
    """High-level LSP indexer that orchestrates language servers and symbol indexing"""
    
    def __init__(self, logger: Logger = None):
        self.logger = logger or Logger(name="k2edit-lsp")
        self.lsp_client = LSPClient(logger=self.logger)
        self.symbol_parser = SymbolParser(logger=self.logger)
        self.file_filter = FileFilter(logger=self.logger)
        self.language_configs = LanguageConfigs()
        self.project_root: Optional[Path] = None
        self.language = None
        
        # Indexes
        self.symbol_index: Dict[str, List[Dict[str, Any]]] = {}
        self.file_index: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self, project_root: str, progress_callback=None):
        """Initialize LSP indexer for project with optional progress callback"""
        self.project_root = Path(project_root)
        await self.logger.info(f"Initializing LSP indexer for project: {self.project_root}")
        
        if progress_callback:
            await progress_callback("Starting symbol indexing...")
            await asyncio.sleep(0.1)
        
        # Detect language and start appropriate server
        self.language = self.file_filter.detect_project_language(self.project_root)
        await self.logger.info(f"Detected language: {self.language}")
        
        if progress_callback:
            await progress_callback(f"Detected language: {self.language}")
            await asyncio.sleep(0.1)
        
        if self.language != "unknown":
            config = LanguageConfigs.get_config(self.language)
            await self.logger.info(f"Starting language server for {self.language}...")
            
            success = await self.lsp_client.start_server(
                self.language, 
                config["command"], 
                self.project_root
            )
            
            if success:
                await self.lsp_client.initialize_connection(self.language, self.project_root)
                if progress_callback:
                    await progress_callback(f"Started {self.language} language server")
            else:
                await self.logger.warning(f"Failed to start {self.language} language server")
                if progress_callback:
                    await progress_callback(f"Failed to start {self.language} language server")
        else:
            await self.logger.warning(f"No language server configured for {self.language}")
            if progress_callback:
                await progress_callback(f"No language server configured for {self.language}")
        
        # Build initial index in background (non-blocking)
        asyncio.create_task(self._build_initial_index_background(progress_callback))
        
        await self.logger.info(f"LSP indexer initialized for {self.language}")
        if progress_callback:
            await progress_callback("Symbol indexing started in background...")
    

    
    async def _build_initial_index_background(self, progress_callback=None):
        """Build initial symbol index for all files in background with progress updates"""
        if self.language == "unknown":
            await self.logger.info("Unknown language detected, skipping initial indexing")
            if progress_callback:
                await progress_callback("Unknown language detected, skipping indexing")
            return
        
        # Get relevant files
        files = self.file_filter.get_project_files(self.project_root, self.language)
        await self.logger.info(f"Starting initial symbol indexing for {self.language} project")
        await self.logger.info(f"Found {len(files)} files to index")
        
        if progress_callback:
            await progress_callback(f"Found {len(files)} files to index")
        
        # Log filtering statistics
        stats = self.file_filter.count_filtered_files(self.project_root, self.language)
        if stats["filtered"] > 0:
            filter_percentage = (stats["filtered"] / stats["total"]) * 100
            await self.logger.info(f"Filtered out {stats['filtered']} files ({filter_percentage:.1f}%)")
        
        # Index each file with progress logging
        indexed_count = 0
        failed_count = 0
        
        for i, file_path in enumerate(files):
            try:
                await self._index_file(file_path)
                indexed_count += 1
                
                # Report progress
                progress = (i + 1) / len(files) * 100
                if progress_callback and (i + 1) % 10 == 0:
                    await progress_callback(f"Indexing symbols... {i + 1}/{len(files)} files ({progress:.1f}%)")
                
                if indexed_count % 20 == 0:
                    await self.logger.info(f"Indexed {indexed_count}/{len(files)} files...")
                    
            except Exception as e:
                failed_count += 1
                await self.logger.warning(f"Failed to index {file_path}: {e}")
        
        await self.logger.info(f"Initial indexing complete: {indexed_count} successful, {failed_count} failed")
        if progress_callback:
            await progress_callback(f"Indexing complete: {indexed_count} files indexed, {failed_count} failed")
    
    async def _index_file(self, file_path: Path):
        """Index a single file for symbols"""
        try:
            relative_path = file_path.relative_to(self.project_root)
            
            await self.logger.debug(f"Indexing symbols for file: {relative_path}")
            
            # Request document symbols
            symbols = await self._get_document_symbols(str(relative_path))
            
            # Count symbol types for this file
            symbol_types = {}
            for symbol in symbols:
                symbol_type = symbol.get("kind", "unknown")
                symbol_types[symbol_type] = symbol_types.get(symbol_type, 0) + 1
            
            await self.logger.debug(f"Found {len(symbols)} symbols in {relative_path}: {symbol_types}")
            
            # Store in index
            self.symbol_index[str(relative_path)] = symbols
            
            # Store file metadata
            file_info = self.file_filter.get_file_info(file_path)
            self.file_index[str(relative_path)] = {
                "language": self.language,
                "size": file_info.get("size", 0),
                "modified": file_info.get("modified", 0),
                "symbols": len(symbols)
            }
            
            # Also notify LSP server about this file to trigger diagnostics
            await self._notify_file_opened(str(file_path.absolute()))
            
        except Exception as e:
            await self.logger.error(f"Failed to index file {file_path}: {e}")
    
    async def _get_document_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """Get symbols from a specific file via LSP"""
        if not self.lsp_client.is_server_running(self.language):
            return []
        
        # Build LSP URI
        uri = f"file://{self.project_root}/{file_path}"
        
        # Request document symbols
        request = {
            "jsonrpc": "2.0",
            "id": 0,  # Will be set by LSP client
            "method": "textDocument/documentSymbol",
            "params": {
                "textDocument": {
                    "uri": uri
                }
            }
        }
        
        try:
            response = await self.lsp_client.send_request(self.language, request)
            if response and "result" in response:
                result = response["result"]
                if isinstance(result, list):
                    return await self.symbol_parser.parse_lsp_symbols(result)
                else:
                    await self.logger.debug(f"Unexpected LSP result format: {type(result)}")
                    return []
        except Exception as e:
            await self.logger.error(f"LSP request failed for {file_path}: {e}")
        
        return []
    
    async def _notify_file_opened(self, file_path: str):
        """Notify LSP server that a file has been opened"""
        try:
            language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
            if language == "unknown" or not self.lsp_client.is_server_running(language):
                return
            
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
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
            
            await self.lsp_client.send_notification(language, did_open_notification)
            await self.logger.info(f"Notified LSP server about opened file: {file_path}")
            
        except Exception as e:
            await self.logger.warning(f"Failed to notify LSP server about opened file: {e}")
    
    # Public API methods
    async def get_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """Get symbols for a specific file"""
        relative_path = str(Path(file_path).relative_to(self.project_root))
        return self.symbol_index.get(relative_path, [])
    
    async def get_dependencies(self, file_path: str) -> List[str]:
        """Get dependencies for a specific file"""
        language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
        return await self.symbol_parser.extract_dependencies(file_path, language)
    
    async def get_project_symbols(self, top_level_only: bool = False) -> List[Dict[str, Any]]:
        """Get symbols across the project, optionally filtering for top-level symbols only"""
        await self.logger.info(f"Starting project-wide symbol fetching (top_level_only={top_level_only})")
        
        all_symbols = []
        total_files = len(self.symbol_index)
        
        await self.logger.info(f"Symbol index contains {total_files} files")
        
        for file_path, symbols in self.symbol_index.items():
            for symbol in symbols:
                # Filter for top-level symbols only if requested
                if top_level_only and symbol.get("parent"):
                    continue
                    
                symbol["file_path"] = file_path
                all_symbols.append(symbol)
        
        # Log statistics
        stats = await self.symbol_parser.get_symbol_statistics(self.symbol_index)
        await self.logger.info(f"Fetched {stats['total_symbols']} total symbols from {stats['total_files']} files")
        await self.logger.info(f"Symbol type breakdown: {stats['symbol_type_breakdown']}")
        
        return all_symbols
    
    async def get_document_outline(self, file_path: str) -> Dict[str, Any]:
        """Get structured outline for a document via LSP"""
        # Ensure appropriate language server is running for this file
        language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
        if language != "unknown" and not self.lsp_client.is_server_running(language):
            config = LanguageConfigs.get_config(language)
            await self.lsp_client.start_server(language, config["command"], self.project_root)
            await self.lsp_client.initialize_connection(language, self.project_root)
        
        # Ensure file is opened with LSP server
        await self._notify_file_opened(file_path)
        
        # Get symbols for this file
        relative_path = str(Path(file_path).relative_to(self.project_root))
        symbols = self.symbol_index.get(relative_path, [])
        
        # Build enhanced outline
        outline = await self.symbol_parser.get_document_outline(symbols, file_path, language)
        
        return outline
    
    async def get_hover_info(self, file_path: str, line: int, character: int) -> Optional[Dict[str, Any]]:
        """Get hover information from LSP server for a specific position"""
        await self.logger.debug(f"get_hover_info: file_path={file_path}, line={line}, character={character}")
        
        language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
        await self.logger.debug(f"Detected language: {language}")
        
        if language == "unknown" or not self.lsp_client.is_server_running(language):
            await self.logger.debug(f"Skipping hover: language={language}, server_running={self.lsp_client.is_server_running(language) if language != 'unknown' else 'N/A'}")
            return None
        
        # Build LSP URI
        uri = f"file://{Path(file_path).absolute()}"
        
        # Request hover information
        request = {
            "jsonrpc": "2.0",
            "id": 0,  # Will be set by LSP client
            "method": "textDocument/hover",
            "params": {
                "textDocument": {
                    "uri": uri
                },
                "position": {
                    "line": line - 1,  # LSP uses 0-based indexing
                    "character": character - 1  # LSP uses 0-based indexing
                }
            }
        }
        
        try:
            response = await self.lsp_client.send_request(language, request)
            await self.logger.debug(f"Hover response received: {response is not None}")
            
            if response and "result" in response and response["result"]:
                await self.logger.debug(f"Hover result contents: {response['result'].get('contents', 'No contents')}")
                return response["result"]
            return None
            
        except Exception as e:
            await self.logger.error(f"Failed to get hover info: {e}")
            return None
    
    async def get_enhanced_context_for_file(self, file_path: str, line: int = None) -> Dict[str, Any]:
        """Get enhanced context for a file including LSP outline"""
        # Ensure appropriate language server is running for this file
        language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
        if language != "unknown" and not self.lsp_client.is_server_running(language):
            config = LanguageConfigs.get_config(language)
            await self.lsp_client.start_server(language, config["command"], self.project_root)
            await self.lsp_client.initialize_connection(language, self.project_root)
        
        # Ensure file is opened with LSP server
        await self._notify_file_opened(file_path)
        
        # Get document outline
        outline = await self.get_document_outline(file_path)
        
        # Get additional LSP information
        symbols = await self.get_symbols(file_path)
        dependencies = await self.get_dependencies(file_path)
        
        return {
            "file_path": file_path,
            "language": language,
            "outline": outline,
            "symbols": symbols,
            "dependencies": dependencies,
            "project_root": str(self.project_root)
        }
    
    async def shutdown(self):
        """Shutdown the LSP indexer and all language servers"""
        await self.lsp_client.shutdown()
        await self.logger.info("LSP indexer shutdown complete")