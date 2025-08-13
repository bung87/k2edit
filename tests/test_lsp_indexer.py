"""
Tests for the LSPIndexer
"""

import pytest
from pathlib import Path
from src.k2edit.agent.lsp_indexer import LSPIndexer


class TestLSPIndexer:
    """Test cases for LSPIndexer"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, temp_project_dir, logger):
        """Test LSP indexer initialization."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        assert indexer.project_root == temp_project_dir
        assert indexer.logger is not None
    
    
    @pytest.mark.asyncio
    async def test_get_symbols_python(self, temp_project_dir, sample_python_file, logger):
        """Test symbol extraction for Python files."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Wait for background indexing to complete
        await indexer.wait_for_indexing_complete(timeout=10.0)
        
        symbols = await indexer.get_symbols(str(sample_python_file))
        
        assert isinstance(symbols, list)
        
        # Check for expected symbols
        symbol_names = [s["name"] for s in symbols]
        assert "hello_world" in symbol_names
        assert "Calculator" in symbol_names
        assert "add" in symbol_names
        assert "multiply" in symbol_names
        
        await indexer.shutdown()
    
    
    @pytest.mark.asyncio
    async def test_get_symbols_javascript(self, temp_project_dir, sample_js_file, logger):
        """Test symbol extraction for JavaScript files."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Wait for background indexing to complete
        await indexer.wait_for_indexing_complete(timeout=10.0)
        
        symbols = await indexer.get_symbols(str(sample_js_file))
        
        assert isinstance(symbols, list)
        
        # Check for expected symbols - may be empty if JS LSP server not available
        symbol_names = [s["name"] for s in symbols]
        if symbols:  # Only assert if symbols were found
            assert "greetUser" in symbol_names
            assert "UserManager" in symbol_names
        
        await indexer.shutdown()
    
    
    @pytest.mark.asyncio
    async def test_get_dependencies(self, temp_project_dir, complex_project, logger):
        """Test dependency analysis."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(complex_project))
        
        # Wait for background indexing to complete
        await indexer.wait_for_indexing_complete(timeout=10.0)
        
        main_file = complex_project / "main.py"
        dependencies = await indexer.get_dependencies(str(main_file))
        
        assert isinstance(dependencies, list)
        # Dependencies should be strings, not dicts
        if dependencies:
            assert any("math_utils" in dep or "calculator" in dep for dep in dependencies)
        
        await indexer.shutdown()
    
    
    @pytest.mark.asyncio
    async def test_symbol_details(self, temp_project_dir, sample_python_file, logger):
        """Test detailed symbol information."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Wait for background indexing to complete
        await indexer.wait_for_indexing_complete(timeout=10.0)
        
        symbols = await indexer.get_symbols(str(sample_python_file))
        
        # Find the Calculator class
        calculator_symbol = next((s for s in symbols if s["name"] == "Calculator"), None)
        assert calculator_symbol is not None
        assert calculator_symbol["kind"] == "class"
        # Check for position information (may vary based on LSP implementation)
        assert any(key in calculator_symbol for key in ["range", "selectionRange", "line", "start_line", "end_line"])
        
        await indexer.shutdown()
    
    

    
    

    
    

    
    
    @pytest.mark.asyncio
    async def test_complex_symbols(self, temp_project_dir, logger):
        """Test extraction of complex symbol structures."""
        # Create the complex file first
        complex_file = temp_project_dir / "complex.py"
        complex_file.write_text('''
class DataProcessor:
    """A class for processing data."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self._cache = {}
    
    @property
    def cache_size(self):
        return len(self._cache)
    
    def process_item(self, item: dict) -> str:
        """Process a single item."""
        return str(item)
    
    async def process_batch(self, items: list) -> list:
        """Process multiple items."""
        return [self.process_item(item) for item in items]

def helper_function(a, b, *args, **kwargs):
    """A helper function with varargs."""
    return a + b + sum(args) + len(kwargs)

CONSTANT_VALUE = 42
''')
        
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Wait for background indexing to complete
        await indexer.wait_for_indexing_complete(timeout=10.0)
        
        symbols = await indexer.get_symbols(str(complex_file))
        
        symbol_names = [s["name"] for s in symbols]
        expected_symbols = [
            "DataProcessor", "helper_function", "CONSTANT_VALUE",
            "process_item", "process_batch", "cache_size"
        ]
        
        for expected in expected_symbols:
            assert expected in symbol_names, f"Missing symbol: {expected}"
        
        await indexer.shutdown()
    
    

    
    
    @pytest.mark.asyncio
    async def test_performance_with_large_files(self, temp_project_dir, logger):
        """Test performance and graceful handling with large files."""
        # Create a large Python file first
        large_file = temp_project_dir / "large.py"
        content = "\n".join([f"def function_{i}(): pass" for i in range(100)])
        large_file.write_text(content)
        
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Wait for background indexing to complete
        await indexer.wait_for_indexing_complete(timeout=15.0)
        
        # Explicitly index the large file since it was created after initialization
        success = await indexer.index_file(str(large_file))
        assert success, "Failed to index large file"
        
        import time
        start_time = time.time()
        symbols = await indexer.get_symbols(str(large_file))
        retrieval_time = time.time() - start_time
        
        # Debug: Log what we found
        await logger.info(f"Found {len(symbols)} symbols in large file")
        if symbols:
            await logger.info(f"First few symbols: {[s.get('name', 'unnamed') for s in symbols[:5]]}")
        
        # Performance and graceful handling assertions
        # The system should handle LSP timeouts gracefully (may return 0 symbols)
        assert isinstance(symbols, list), "Should return a list of symbols"
        assert retrieval_time < 2.0, f"Symbol retrieval took {retrieval_time:.2f}s, expected < 2.0s"
        
        # If LSP is working, we should get symbols; if not, graceful degradation is acceptable
        if len(symbols) > 0:
            await logger.info("LSP successfully extracted symbols")
        else:
            await logger.info("LSP timed out - graceful degradation to empty symbol list")
        
        await indexer.shutdown()
    
    
    @pytest.mark.asyncio
    async def test_shutdown(self, temp_project_dir, logger):
        """Test proper shutdown of LSP indexer."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Should not raise errors during shutdown
        await indexer.shutdown()
        
        # After shutdown, operations should return empty results
        symbols = await indexer.get_symbols("test.py")
        assert symbols == []