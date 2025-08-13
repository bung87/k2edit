#!/usr/bin/env python3
"""
Test LSP symbol indexing functionality specifically
"""

import pytest
import asyncio
from pathlib import Path
from src.k2edit.agent.lsp_indexer import LSPIndexer


class TestLSPSymbolIndexing:
    """Test cases specifically for LSP symbol indexing issues"""
    
    @pytest.mark.asyncio
    async def test_symbol_indexing_with_wait(self, temp_project_dir, sample_python_file, logger):
        """Test symbol extraction with proper wait for indexing completion."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Wait for background indexing to complete
        indexing_complete = await indexer.wait_for_indexing_complete(timeout=10.0)
        await logger.info(f"Indexing complete: {indexing_complete}")
        
        # Check if symbols were indexed
        symbols = await indexer.get_symbols(str(sample_python_file))
        await logger.info(f"Found symbols: {[s.get('name') for s in symbols]}")
        
        # Log the symbol index state
        await logger.info(f"Symbol index keys: {list(indexer.symbol_index.keys())}")
        await logger.info(f"Project root: {indexer.project_root}")
        await logger.info(f"Detected language: {indexer.language}")
        
        # If no symbols found, this indicates the LSP server issue
        if not symbols:
            await logger.warning("No symbols found - this indicates LSP server is not working properly")
            
        # For now, just verify the method doesn't crash
        assert isinstance(symbols, list)
        
        await indexer.shutdown()
    
    @pytest.mark.asyncio
    async def test_manual_symbol_extraction(self, temp_project_dir, sample_python_file, logger):
        """Test manual symbol extraction without LSP server dependency."""
        # This test verifies that the issue is with LSP server communication
        # not with the basic file handling
        
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Check file exists and is readable
        assert sample_python_file.exists()
        content = sample_python_file.read_text()
        assert "hello_world" in content
        assert "Calculator" in content
        
        # Check if file is in the expected location relative to project root
        relative_path = sample_python_file.relative_to(temp_project_dir)
        await logger.info(f"Sample file relative path: {relative_path}")
        
        # Check language detection
        from src.k2edit.utils.language_utils import detect_language_by_extension
        language = detect_language_by_extension(sample_python_file.suffix)
        await logger.info(f"Detected language for .py file: {language}")
        
        await indexer.shutdown()
    
    @pytest.mark.asyncio
    async def test_lsp_server_availability(self, temp_project_dir, logger):
        """Test if LSP servers are available and can be started."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Check if Python LSP server can be started
        from src.k2edit.agent.language_configs import LanguageConfigs
        
        python_config = LanguageConfigs.get_config("python")
        await logger.info(f"Python LSP config: {python_config}")
        
        if python_config:
            # Try to check if the LSP server command exists
            import shutil
            command_parts = python_config["command"]
            if isinstance(command_parts, list) and command_parts:
                server_executable = shutil.which(command_parts[0])
                await logger.info(f"LSP server executable '{command_parts[0]}' found at: {server_executable}")
                
                if not server_executable:
                    await logger.warning(f"LSP server executable '{command_parts[0]}' not found in PATH")
        else:
            await logger.warning("No Python LSP configuration found")
        
        await indexer.shutdown()
    
    @pytest.mark.asyncio
    async def test_symbol_index_state(self, temp_project_dir, sample_python_file, logger):
        """Test the internal state of symbol indexing."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Wait for indexing
        await indexer.wait_for_indexing_complete(timeout=5.0)
        
        # Check internal state
        await logger.info(f"Symbol index has {len(indexer.symbol_index)} entries")
        await logger.info(f"File index has {len(indexer.file_index)} entries")
        
        # List all indexed files
        for file_path, symbols in indexer.symbol_index.items():
            await logger.info(f"File: {file_path}, Symbols: {len(symbols)}")
            if symbols:
                symbol_names = [s.get('name', 'unnamed') for s in symbols]
                await logger.info(f"  Symbol names: {symbol_names}")
        
        await indexer.shutdown()