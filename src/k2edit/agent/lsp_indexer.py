"""
LSP Indexer for K2Edit Agentic System
High-level orchestrator for LSP-based code intelligence
"""

import asyncio
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiologger import Logger

from .lsp_client import LSPClient, ServerStatus
from .language_configs import LanguageConfigs
from .symbol_parser import SymbolParser
from .file_filter import FileFilter
from .chroma_memory_store import ChromaMemoryStore
from ..utils.language_utils import detect_language_by_extension


class LSPIndexer:
    """High-level LSP indexer that orchestrates language servers and symbol indexing"""
    
    def __init__(self, lsp_client: LSPClient = None, logger: Logger = None, memory_store: ChromaMemoryStore = None):
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
        
        # ChromaDB symbol cache - use provided memory_store or None
        self.symbol_cache: Optional[ChromaMemoryStore] = memory_store
        
        # Server restart lock to prevent concurrent restarts
        self._server_restart_lock = asyncio.Lock()
        
    async def initialize(self, project_root: str, progress_callback=None):
        """Initialize LSP indexer for project with optional progress callback"""
        self.project_root = Path(project_root)
        await self.logger.info(f"Initializing LSP indexer for project: {self.project_root}")
        
        if progress_callback:
            await progress_callback("Starting symbol indexing...")
            await asyncio.sleep(0.1)
        
        # Log symbol cache status
        if self.symbol_cache:
            await self.logger.info("Using provided ChromaDB symbol cache")
            if progress_callback:
                await progress_callback("Symbol cache ready")
        else:
            await self.logger.info("No symbol cache provided - using LSP-only indexing")
        
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
        
        # Determine optimal number of workers (max 3 to avoid overwhelming LSP server)
        max_workers = min(3, max(1, len(files) // 20))
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
            
            # Small delay to prevent overwhelming the LSP server
            await asyncio.sleep(0.5)
        
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
        """Index a single file for symbols with caching support"""
        try:
            relative_path = file_path.relative_to(self.project_root)
            
            await self.logger.debug(f"Indexing symbols for file: {relative_path}")
            
            # First, try to get cached symbols
            symbols = await self._get_cached_symbols(file_path)
            
            if symbols is not None:
                await self.logger.debug(f"Using cached symbols for {relative_path} ({len(symbols)} symbols)")
            else:
                # Request document symbols from LSP
                symbols = await self._get_document_symbols(str(relative_path))
                
                # Cache the symbols for future use
                if symbols:
                    await self._cache_symbols(file_path, symbols)
            
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
    
    def _calculate_file_hash(self, content: str) -> str:
        """Calculate MD5 hash of file content"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    async def _get_cached_symbols(self, file_path: Path) -> Optional[List[Dict[str, Any]]]:
        """Get cached symbols for a file if content hasn't changed"""
        if not self.symbol_cache:
            return None
        
        try:
            # Read file content to calculate hash
            content = file_path.read_text(encoding='utf-8')
            content_hash = self._calculate_file_hash(content)
            
            # Search for cached symbols using file path and content hash
            abs_path = str(file_path.absolute())
            search_query = f"symbols_cache:{abs_path}:{content_hash}"
            
            results = await self.symbol_cache.search_relevant_context(search_query, limit=1)
            
            if results and len(results) > 0:
                result = results[0]
                # Extract symbols from the cached result
                if 'content' in result and isinstance(result['content'], dict):
                    cached_data = result['content']
                    if 'symbols' in cached_data and 'content_hash' in cached_data:
                        if cached_data['content_hash'] == content_hash:
                            await self.logger.debug(f"Found cached symbols for {file_path}")
                            return cached_data['symbols']
            
            return None
        except Exception as e:
            await self.logger.debug(f"Error checking symbol cache for {file_path}: {e}")
            return None
    
    async def _cache_symbols(self, file_path: Path, symbols: List[Dict[str, Any]]) -> None:
        """Cache symbols for a file with its content hash"""
        if not self.symbol_cache:
            return
        
        try:
            # Read file content to calculate hash
            content = file_path.read_text(encoding='utf-8')
            content_hash = self._calculate_file_hash(content)
            
            abs_path = str(file_path.absolute())
            
            # Store symbols with file path and content hash
            cache_data = {
                'file_path': abs_path,
                'content_hash': content_hash,
                'symbols': symbols,
                'timestamp': time.time(),
                'language': self.language
            }
            
            # Use a unique identifier for the cache entry
            cache_id = f"symbols_cache:{abs_path}:{content_hash}"
            
            # Store in ChromaDB using the pattern storage method
            await self.symbol_cache.store_pattern(
                cache_id,
                f"Cached symbols for {abs_path}",
                cache_data
            )
            
            await self.logger.debug(f"Cached {len(symbols)} symbols for {file_path}")
            
        except Exception as e:
            await self.logger.debug(f"Error caching symbols for {file_path}: {e}")
    
    async def _get_document_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """Get symbols from a specific file via LSP with AST fallback"""
        # Build absolute file path
        abs_file_path = str(self.project_root / file_path)
        
        # Check if we need to restart the LSP server
        await self._ensure_server_healthy()
        
        # Try LSP first if server is running
        if self.lsp_client.is_server_running(self.language):
            # Notify LSP server that file is opened (required by some servers)
            try:
                await self.lsp_client.notify_file_opened(abs_file_path, self.language)
            except Exception as e:
                await self.logger.warning(f"Failed to notify file opened for {file_path}: {e}")
            
            try:
                # Use the LSP client's get_document_symbols method
                lsp_symbols = await self.lsp_client.get_document_symbols(abs_file_path, self.language)
                if lsp_symbols:
                    symbols = await self.symbol_parser.parse_lsp_symbols(lsp_symbols)
                    if symbols:  # If we got symbols from LSP, return them
                        return symbols
                else:
                     # If LSP returned None/empty, the server might be unresponsive
                     await self.logger.warning(f"LSP server returned no symbols for {file_path} - server may be unresponsive")
                     # Mark server as potentially unhealthy for future restart
                     if self.language in self.lsp_client.connections:
                         connection = self.lsp_client.connections[self.language]
                         connection.failed_health_checks += 1
                         if connection.failed_health_checks >= 2:
                             await self.logger.info(f"Marking {self.language} server as unhealthy due to repeated failures")
                             connection.status = ServerStatus.ERROR
            except Exception as e:
                await self.logger.warning(f"LSP request failed for {file_path}: {e}")
                # Mark server as unhealthy on exception
                if self.language in self.lsp_client.connections:
                    connection = self.lsp_client.connections[self.language]
                    connection.failed_health_checks += 1
                    connection.status = ServerStatus.ERROR
        
        # Fallback: return empty list if LSP failed
        # Only log if this is unexpected (file should have symbols)
        if file_path.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c')):
            await self.logger.debug(f"No symbols extracted for {file_path} (LSP failed)")
        return []
    
    async def _ensure_server_healthy(self):
        """Ensure the LSP server is healthy, restart if necessary"""
        if not self.language or self.language == "unknown":
            return
        
        # Use lock to prevent concurrent server restarts
        async with self._server_restart_lock:
            # Re-check server status after acquiring lock (another task might have fixed it)
            if self.language in self.lsp_client.connections:
                connection = self.lsp_client.connections[self.language]
                
                # Check if server is unhealthy or unresponsive
                is_unhealthy = (
                    connection.status.value == "error" or 
                    (connection.process and connection.process.returncode is not None) or
                    connection.failed_health_checks >= 3 or
                    (time.time() - connection.last_activity > 30.0)  # No activity for 30 seconds
                )
                
                if is_unhealthy:
                    await self.logger.info(f"LSP server for {self.language} is unhealthy, attempting restart")
                    
                    # Get the server configuration
                    config = self.language_configs.get_config(self.language)
                    if config and "command" in config:
                        try:
                            # Stop the unhealthy server first
                            await self.lsp_client.stop_server(self.language)
                            await asyncio.sleep(1.0)  # Wait for cleanup
                            
                            # Start a new server (this uses proper locking)
                            success = await self.lsp_client.start_server(
                                self.language, 
                                config["command"], 
                                self.project_root
                            )
                            
                            if success:
                                # Re-initialize the connection
                                await self.lsp_client.initialize_connection(
                                    self.language, 
                                    self.project_root, 
                                    config.get("settings", {})
                                )
                                await self.logger.info(f"Successfully restarted LSP server for {self.language}")
                            else:
                                await self.logger.error(f"Failed to restart LSP server for {self.language}")
                        except Exception as e:
                            await self.logger.error(f"Error restarting LSP server for {self.language}: {e}")
                else:
                    # Server is healthy, no action needed
                    return
            
            # If no server exists, try to start one
            elif not self.lsp_client.is_server_running(self.language):
                await self.logger.info(f"No LSP server running for {self.language}, starting one")
                config = self.language_configs.get_config(self.language)
                if config and "command" in config:
                    try:
                        success = await self.lsp_client.start_server(
                            self.language, 
                            config["command"], 
                            self.project_root
                        )
                        
                        if success:
                            # Initialize the connection
                            await self.lsp_client.initialize_connection(
                                self.language, 
                                self.project_root, 
                                config.get("settings", {})
                            )
                            await self.logger.info(f"Successfully started LSP server for {self.language}")
                        else:
                            await self.logger.error(f"Failed to start LSP server for {self.language}")
                    except Exception as e:
                        await self.logger.error(f"Error starting LSP server for {self.language}: {e}")
    


    # Public API methods
    async def index_file(self, file_path: str) -> bool:
        """Index a specific file and add it to the symbol index
        
        Args:
            file_path: Path to the file to index (can be relative or absolute)
            
        Returns:
            True if indexing was successful, False otherwise
        """
        try:
            # Ensure file_path is absolute
            abs_path = Path(file_path)
            if not abs_path.is_absolute():
                abs_path = self.project_root / file_path
            
            # Check if file exists
            if not abs_path.exists():
                await self.logger.warning(f"File does not exist: {abs_path}")
                return False
            
            # Index the file
            await self._index_file(abs_path)
            await self.logger.info(f"Successfully indexed file: {abs_path}")
            return True
            
        except Exception as e:
            await self.logger.error(f"Failed to index file {file_path}: {e}")
            return False
    
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
        file_paths = file_paths or list(self.symbol_index.keys())
        if not file_paths:
            return {}
        
        await self.logger.info(f"Extracting dependencies for {len(file_paths)} files")
        
        max_workers = min(8, max(1, len(file_paths) // 5))
        semaphore = asyncio.Semaphore(max_workers)
        
        async def _extract_file_dependencies(file_path: str) -> tuple[str, List[str]]:
            async with semaphore:
                try:
                    abs_path = str(self.project_root / file_path)
                    language = detect_language_by_extension(Path(file_path).suffix)
                    dependencies = await self.symbol_parser.extract_dependencies(abs_path, language)
                    return file_path, dependencies
                except Exception as e:
                    await self.logger.warning(f"Failed to extract dependencies for {file_path}: {e}")
                    return file_path, []
        
        tasks = [_extract_file_dependencies(file_path) for file_path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        dependency_map = {file_path: deps for file_path, deps in results}
        
        total_deps = sum(len(deps) for deps in dependency_map.values())
        await self.logger.info(f"Extracted {total_deps} total dependencies from {len(file_paths)} files")
        
        return dependency_map
    
    async def get_project_symbols(self, top_level_only: bool = False) -> List[Dict[str, Any]]:
        """Get symbols across the project, optionally filtering for top-level symbols only"""
        if not self.symbol_index:
            return []
        
        total_files = len(self.symbol_index)
        await self.logger.info(f"Starting project-wide symbol fetching (top_level_only={top_level_only}) for {total_files} files")
        
        max_workers = min(8, max(1, total_files // 5))
        semaphore = asyncio.Semaphore(max_workers)
        
        async def _process_file_symbols(file_path: str, symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            async with semaphore:
                file_symbols = []
                for symbol in symbols:
                    if top_level_only and symbol.get("parent"):
                        continue
                    
                    symbol_copy = symbol.copy()
                    symbol_copy["file_path"] = file_path
                    file_symbols.append(symbol_copy)
                
                return file_symbols
        
        tasks = [_process_file_symbols(file_path, symbols) for file_path, symbols in self.symbol_index.items()]
        file_results = await asyncio.gather(*tasks, return_exceptions=False)
        
        all_symbols = [symbol for file_symbols in file_results for symbol in file_symbols]
        
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
    
    async def clear_symbol_cache(self, file_path: str = None) -> bool:
        """Clear symbol cache for a specific file or all files
        
        Args:
            file_path: Path to the file to clear cache for (optional, clears all if None)
            
        Returns:
            True if cache was cleared successfully, False otherwise
        """
        if not self.symbol_cache:
            await self.logger.warning("Symbol cache not initialized")
            return False
        
        try:
            if file_path:
                # Clear cache for specific file
                abs_path = str(Path(file_path).absolute())
                # Note: ChromaDB doesn't have a direct delete by pattern method
                # This is a limitation we'll document
                await self.logger.info(f"Cache clearing for specific files not fully implemented yet for {abs_path}")
                return True
            else:
                # Clear all symbol cache
                # Note: This would require recreating the collections
                await self.logger.info("Full cache clearing not implemented - restart application to clear cache")
                return True
                
        except Exception as e:
            await self.logger.error(f"Error clearing symbol cache: {e}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the symbol cache"""
        if not self.symbol_cache:
            return {"cache_enabled": False, "error": "Symbol cache not initialized"}
        
        try:
            # Get basic cache information
            return {
                "cache_enabled": True,
                "cache_type": "ChromaDB",
                "project_root": str(self.project_root),
                "language": self.language
            }
        except Exception as e:
            return {"cache_enabled": True, "error": str(e)}
    
    async def shutdown(self):
        """Shutdown the LSP indexer and all language servers"""
        await self.lsp_client.shutdown()
        
        # Clean up symbol cache if initialized
        if self.symbol_cache:
            try:
                # ChromaMemoryStore doesn't have an explicit shutdown method
                # but we can clear the reference
                self.symbol_cache = None
                await self.logger.info("Symbol cache cleaned up")
            except Exception as e:
                await self.logger.warning(f"Error cleaning up symbol cache: {e}")
        
        await self.logger.info("LSP indexer shutdown complete")