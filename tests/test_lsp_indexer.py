"""
Tests for the LSPIndexer
"""

import pytest
import asyncio
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
        
        symbols = await indexer.get_symbols(str(sample_python_file))
        
        assert isinstance(symbols, list)
        
        # Check for expected symbols
        symbol_names = [s["name"] for s in symbols]
        assert "hello_world" in symbol_names
        assert "Calculator" in symbol_names
        assert "add" in symbol_names
        assert "multiply" in symbol_names
    
    
    @pytest.mark.asyncio
    async def test_get_symbols_javascript(self, temp_project_dir, sample_js_file, logger):
        """Test symbol extraction for JavaScript files."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        symbols = await indexer.get_symbols(str(sample_js_file))
        
        assert isinstance(symbols, list)
        
        # Check for expected symbols
        symbol_names = [s["name"] for s in symbols]
        assert "greetUser" in symbol_names
        assert "UserManager" in symbol_names
    
    
    @pytest.mark.asyncio
    async def test_get_dependencies(self, temp_project_dir, complex_project, logger):
        """Test dependency analysis."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(complex_project))
        
        main_file = complex_project / "main.py"
        dependencies = await indexer.get_dependencies(str(main_file))
        
        assert isinstance(dependencies, list)
        # Should contain imports from math_utils and calculator
        dep_names = [d["name"] for d in dependencies]
        assert any("math_utils" in str(d.get("name", "")) or "calculator" in str(d.get("name", "")) for d in dependencies)
    
    

    
    

    
    

    
    
    @pytest.mark.asyncio
    async def test_symbol_details(self, temp_project_dir, sample_python_file, logger):
        """Test detailed symbol information."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        symbols = await indexer.get_symbols(str(sample_python_file))
        
        # Check symbol details
        calculator_class = next((s for s in symbols if s["name"] == "Calculator"), None)
        assert calculator_class is not None
        assert calculator_class["kind"] == "class"
        assert "line" in calculator_class
        assert "column" in calculator_class
        
        hello_func = next((s for s in symbols if s["name"] == "hello_world"), None)
        assert hello_func is not None
        assert hello_func["kind"] == "function"
    
    

    
    

    
    

    
    
    @pytest.mark.asyncio
    async def test_complex_symbols(self, temp_project_dir, logger):
        """Test extraction of complex symbol structures."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
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
        
        symbols = await indexer.get_symbols(str(complex_file))
        
        symbol_names = [s["name"] for s in symbols]
        expected_symbols = [
            "DataProcessor", "helper_function", "CONSTANT_VALUE",
            "process_item", "process_batch", "cache_size"
        ]
        
        for expected in expected_symbols:
            assert expected in symbol_names, f"Missing symbol: {expected}"
    
    

    
    
    @pytest.mark.asyncio
    async def test_performance_with_large_files(self, temp_project_dir, logger):
        """Test performance with large files."""
        indexer = LSPIndexer(logger=logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Create large file
        large_file = temp_project_dir / "large.py"
        content = []
        for i in range(1000):
            content.append(f"def func{i}():\n    return {i}")
        large_file.write_text("\n\n".join(content))
        
        # Should handle large files efficiently
        symbols = await indexer.get_symbols(str(large_file))
        assert len(symbols) >= 1000
        
        info = await indexer.get_file_info(str(large_file))
        assert info["lines"] >= 1000
    
    
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