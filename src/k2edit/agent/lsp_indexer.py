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
    
    def __init__(self, lsp_client: LSPClient = None, logger: Logger = None):
        # Only use aiologger.Logger
        self.logger = logger or Logger(name="k2edit-lsp")
            
        self.lsp_client = lsp_client or LSPClient(logger=self.logger)
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
            await asyncio.sleep(0.1)
        
        # Start language server
        config = LanguageConfigs.get_config(self.language)
        if config:
            success = await self.lsp_client.start_server(
                self.language, 
                config["command"], 
                self.project_root
            )
            
            if success:
                await self.lsp_client.initialize_connection(self.language, self.project_root)
                await self.logger.info(f"Successfully started {self.language} language server")
                if progress_callback:
                    await progress_callback(f"Started {self.language} language server")
            else:
                await self.logger.warning(f"Failed to start {self.language} language server")
                if progress_callback:
                    await progress_callback(f"Failed to start {self.language} language server")
        else:
            await self.logger.warning(f"No configuration found for {self.language}")
            if progress_callback:
                await progress_callback(f"No language server configuration for {self.language}")
        
        # Build initial index in background (non-blocking)
        self._indexing_task = asyncio.create_task(self._build_initial_index_background(progress_callback))
        
        await self.logger.info(f"LSP indexer initialized for {self.language}")
        if progress_callback:
            await progress_callback("Symbol indexing started in background...")
    
    async def ensure_language_server(self, language: str) -> bool:
        """Ensure LSP server is running for the given language"""
        if self.lsp_client.is_server_running(language):
            await self.logger.debug(f"LSP server for {language} already running")
            return True
        
        return False
    

    
    async def _build_initial_index_background(self, progress_callback=None):
        """Build initial symbol index for all files in background with progress updates using concurrent processing"""
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
        
        # Index files concurrently with progress logging
        indexed_count = 0
        failed_count = 0
        
        # Determine optimal number of workers (max 8 to avoid overwhelming LSP server)
        max_workers = min(8, max(1, len(files) // 10))
        await self.logger.info(f"Using {max_workers} concurrent workers for indexing")
        
        # Process files in batches to manage memory and provide progress updates
        batch_size = max(10, len(files) // 20)  # Process in batches for better progress reporting
        
        for batch_start in range(0, len(files), batch_size):
            batch_end = min(batch_start + batch_size, len(files))
            batch_files = files[batch_start:batch_end]
            
            # Process current batch concurrently
            batch_results = await self._index_files_batch(batch_files, max_workers)
            
            # Update counters
            for success in batch_results:
                if success:
                    indexed_count += 1
                else:
                    failed_count += 1
            
            # Report progress
            total_processed = batch_end
            progress = total_processed / len(files) * 100
            if progress_callback:
                await progress_callback(f"Indexing symbols... {total_processed}/{len(files)} files ({progress:.1f}%)")
            
            await self.logger.info(f"Batch complete: {indexed_count}/{total_processed} files indexed...")
        
        await self.logger.info(f"Initial indexing complete: {indexed_count} successful, {failed_count} failed")
        if progress_callback:
            await progress_callback(f"Indexing complete: {indexed_count} files indexed, {failed_count} failed")
    
    async def _index_files_batch(self, files: List[Path], max_workers: int) -> List[bool]:
        """Index a batch of files concurrently using asyncio semaphore for controlled concurrency"""
        # Use semaphore to limit concurrent operations to avoid overwhelming the LSP server
        semaphore = asyncio.Semaphore(max_workers)
        
        async def _index_file_with_semaphore(file_path: Path) -> bool:
            """Index a single file with semaphore control"""
            async with semaphore:
                try:
                    await self._index_file(file_path)
                    await self.logger.debug(f"Successfully indexed: {file_path}")
                    return True
                except Exception as e:
                    await self.logger.warning(f"Failed to index {file_path}: {e}")
                    return False
        
        # Execute all file indexing tasks concurrently with controlled concurrency
        tasks = [_index_file_with_semaphore(file_path) for file_path in files]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        return results
    
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
            await self.logger.aerror(f"LSP request failed for {file_path}: {e}")
        
        return []
    

    
    # Public API methods
    async def get_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """Get symbols for a specific file"""
        try:
            # Ensure file_path is absolute
            abs_path = Path(file_path)
            if not abs_path.is_absolute():
                abs_path = self.project_root / file_path
            relative_path = str(abs_path.relative_to(self.project_root))
            return self.symbol_index.get(relative_path, [])
        except ValueError:
            # If file is not within project root, return empty list
            return []
    
    async def get_dependencies(self, file_path: str) -> List[str]:
        """Get dependencies for a specific file"""
        try:
            # Ensure file_path is absolute
            abs_path = Path(file_path)
            if not abs_path.is_absolute():
                abs_path = self.project_root / file_path
            language = detect_language_by_extension(abs_path.suffix)
            return await self.symbol_parser.extract_dependencies(str(abs_path), language)
        except Exception as e:
            await self.logger.error(f"Error getting dependencies for {file_path}: {e}")
            return []
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file information from the file index"""
        try:
            # Ensure file_path is absolute
            abs_path = Path(file_path)
            if not abs_path.is_absolute():
                abs_path = self.project_root / file_path
            relative_path = str(abs_path.relative_to(self.project_root))
            return self.file_index.get(relative_path, {})
        except ValueError:
            # If file is not within project root, return empty dict
            return {}
    
    async def find_symbol_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find references to a symbol across the project"""
        references = []
        
        # Search through all indexed files for the symbol
        for file_path, symbols in self.symbol_index.items():
            for symbol in symbols:
                if symbol.get("name") == symbol_name:
                    references.append({
                        "file_path": file_path,
                        "line": symbol.get("line", 0),
                        "column": symbol.get("column", 0),
                        "kind": symbol.get("kind", "unknown")
                    })
        
        return references
    
    async def wait_for_indexing_complete(self, timeout: float = 30.0) -> bool:
        """Wait for background indexing to complete
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if indexing completed successfully, False if timeout or error
        """
        if not hasattr(self, '_indexing_task') or self._indexing_task is None:
            return True  # No indexing task, consider it complete
        
        try:
            await asyncio.wait_for(self._indexing_task, timeout=timeout)
            return True
        except asyncio.TimeoutError:
            await self.logger.warning(f"Indexing did not complete within {timeout} seconds")
            return False
        except Exception as e:
            await self.logger.error(f"Error waiting for indexing completion: {e}")
            return False
    
    async def get_project_dependencies(self, file_paths: List[str] = None) -> Dict[str, List[str]]:
        """Get dependencies for multiple files concurrently"""
        if file_paths is None:
            # Get all indexed files
            file_paths = list(self.symbol_index.keys())
        
        if not file_paths:
            return {}
        
        await self.logger.info(f"Extracting dependencies for {len(file_paths)} files")
        
        # Process files concurrently for better performance
        max_workers = min(8, max(1, len(file_paths) // 5))
        semaphore = asyncio.Semaphore(max_workers)
        
        async def _extract_file_dependencies(file_path: str) -> tuple[str, List[str]]:
            """Extract dependencies for a single file"""
            async with semaphore:
                try:
                    # Convert relative path to absolute for dependency extraction
                    abs_path = str(self.project_root / file_path)
                    language = detect_language_by_extension(Path(file_path).suffix)
                    dependencies = await self.symbol_parser.extract_dependencies(abs_path, language)
                    return file_path, dependencies
                except Exception as e:
                    await self.logger.warning(f"Failed to extract dependencies for {file_path}: {e}")
                    return file_path, []
        
        # Create tasks for concurrent processing
        tasks = [_extract_file_dependencies(file_path) for file_path in file_paths]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Build dependency map
        dependency_map = {file_path: deps for file_path, deps in results}
        
        total_deps = sum(len(deps) for deps in dependency_map.values())
        await self.logger.info(f"Extracted {total_deps} total dependencies from {len(file_paths)} files")
        
        return dependency_map
    
    async def get_project_symbols(self, top_level_only: bool = False) -> List[Dict[str, Any]]:
        """Get symbols across the project, optionally filtering for top-level symbols only with concurrent processing"""
        await self.logger.info(f"Starting project-wide symbol fetching (top_level_only={top_level_only})")
        
        total_files = len(self.symbol_index)
        await self.logger.info(f"Symbol index contains {total_files} files")
        
        if not self.symbol_index:
            return []
        
        # Process files concurrently for better performance with large projects
        max_workers = min(8, max(1, total_files // 5))
        semaphore = asyncio.Semaphore(max_workers)
        
        async def _process_file_symbols(file_path: str, symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Process symbols from a single file with filtering"""
            async with semaphore:
                file_symbols = []
                for symbol in symbols:
                    # Filter for top-level symbols only if requested
                    if top_level_only and symbol.get("parent"):
                        continue
                    
                    # Create a copy to avoid modifying the original
                    symbol_copy = symbol.copy()
                    symbol_copy["file_path"] = file_path
                    file_symbols.append(symbol_copy)
                
                return file_symbols
        
        # Create tasks for concurrent processing
        tasks = [
            _process_file_symbols(file_path, symbols)
            for file_path, symbols in self.symbol_index.items()
        ]
        
        # Execute all tasks concurrently
        file_results = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Flatten results
        all_symbols = []
        for file_symbols in file_results:
            all_symbols.extend(file_symbols)
        
        # Log statistics
        stats = await self.symbol_parser.get_symbol_statistics(self.symbol_index)
        await self.logger.info(f"Fetched {stats['total_symbols']} total symbols from {stats['total_files']} files")
        await self.logger.info(f"Symbol type breakdown: {stats['symbol_type_breakdown']}")
        
        return all_symbols
    
    async def get_document_outline(self, file_path: str) -> Dict[str, Any]:
        """Get structured outline for a document via LSP"""
        # Ensure appropriate language server is running for this file
        language = detect_language_by_extension(Path(file_path).suffix)
        if language != "unknown" and not self.lsp_client.is_server_running(language):
            config = LanguageConfigs.get_config(language)
            await self.lsp_client.start_server(language, config["command"], self.project_root)
            await self.lsp_client.initialize_connection(language, self.project_root)
        
        # Ensure file is opened with LSP server
        await self.lsp_client.notify_file_opened(file_path, language)
        
        # Get symbols for this file
        relative_path = str(Path(file_path).relative_to(self.project_root))
        symbols = self.symbol_index.get(relative_path, [])
        
        # Build enhanced outline
        outline = await self.symbol_parser.get_document_outline(symbols, file_path, language)
        
        return outline
    
    async def shutdown(self):
        """Shutdown the LSP indexer and all language servers"""
        await self.lsp_client.shutdown()
        await self.logger.info("LSP indexer shutdown complete")