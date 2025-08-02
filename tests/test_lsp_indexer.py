"""
Tests for the LSPIndexer
"""

import pytest
import asyncio
from pathlib import Path
from agent.lsp_indexer import LSPIndexer


class TestLSPIndexer:
    """Test cases for LSPIndexer"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, temp_project_dir, logger):
        """Test LSP indexer initialization."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(temp_project_dir))
        
        assert indexer.project_root == temp_project_dir
        assert indexer.logger is not None
    
    
    @pytest.mark.asyncio
    async def test_get_symbols_python(self, temp_project_dir, sample_python_file, logger):
        """Test symbol extraction for Python files."""
        indexer = LSPIndexer(logger)
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
        indexer = LSPIndexer(logger)
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
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(complex_project))
        
        main_file = complex_project / "main.py"
        dependencies = await indexer.get_dependencies(str(main_file))
        
        assert isinstance(dependencies, list)
        # Should contain imports from math_utils and calculator
        dep_names = [d["name"] for d in dependencies]
        assert any("math_utils" in str(d.get("name", "")) or "calculator" in str(d.get("name", "")) for d in dependencies)
    
    
    @pytest.mark.asyncio
    async def test_get_file_info(self, temp_project_dir, sample_python_file, logger):
        """Test getting file information."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(temp_project_dir))
        
        info = await indexer.get_file_info(str(sample_python_file))
        
        assert "language" in info
        assert "size" in info
        assert "lines" in info
        assert info["language"] == "python"
        assert info["size"] > 0
    
    
    @pytest.mark.asyncio
    async def test_find_symbol_references(self, temp_project_dir, complex_project, logger):
        """Test finding symbol references."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(complex_project))
        
        # Find references to 'add' function
        references = await indexer.find_symbol_references("add")
        
        assert isinstance(references, list)
        # Should find references in calculator.py and main.py
        files = [r["file_path"] for r in references]
        assert any("calculator.py" in f or "main.py" in f for f in files)
    
    
    @pytest.mark.asyncio
    async def test_refresh_index(self, temp_project_dir, sample_python_file, logger):
        """Test refreshing the index."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Initial indexing
        symbols1 = await indexer.get_symbols(str(sample_python_file))
        
        # Modify file
        sample_python_file.write_text(sample_python_file.read_text() + "\ndef new_function(): pass")
        
        # Refresh index
        await indexer.refresh_index(str(sample_python_file))
        
        # Check for new symbols
        symbols2 = await indexer.get_symbols(str(sample_python_file))
        
        assert len(symbols2) >= len(symbols1)
    
    
    @pytest.mark.asyncio
    async def test_symbol_details(self, temp_project_dir, sample_python_file, logger):
        """Test detailed symbol information."""
        indexer = LSPIndexer(logger)
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
    async def test_language_detection(self, temp_project_dir, logger):
        """Test language detection for different file types."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Test Python file
        py_file = temp_project_dir / "test.py"
        py_file.write_text("def test(): pass")
        
        info = await indexer.get_file_info(str(py_file))
        assert info["language"] == "python"
        
        # Test JavaScript file
        js_file = temp_project_dir / "test.js"
        js_file.write_text("function test() {}")
        
        info = await indexer.get_file_info(str(js_file))
        assert info["language"] == "javascript"
    
    
    @pytest.mark.asyncio
    async def test_empty_file(self, temp_project_dir, logger):
        """Test handling of empty files."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(temp_project_dir))
        
        empty_file = temp_project_dir / "empty.py"
        empty_file.write_text("")
        
        symbols = await indexer.get_symbols(str(empty_file))
        assert symbols == []
        
        info = await indexer.get_file_info(str(empty_file))
        assert info["size"] == 0
        assert info["lines"] == 0
    
    
    @pytest.mark.asyncio
    async def test_nonexistent_file(self, temp_project_dir, logger):
        """Test handling of nonexistent files."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(temp_project_dir))
        
        nonexistent = temp_project_dir / "nonexistent.py"
        
        symbols = await indexer.get_symbols(str(nonexistent))
        assert symbols == []
        
        info = await indexer.get_file_info(str(nonexistent))
        assert info["language"] == "unknown"
    
    
    @pytest.mark.asyncio
    async def test_complex_symbols(self, temp_project_dir, logger):
        """Test extraction of complex symbol structures."""
        indexer = LSPIndexer(logger)
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
    async def test_cross_file_references(self, temp_project_dir, complex_project, logger):
        """Test finding references across files."""
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(complex_project))
        
        # Find all references to Calculator class
        references = await indexer.find_symbol_references("Calculator")
        
        # Should find references in multiple files
        files = set(r["file_path"] for r in references)
        assert len(files) >= 2  # At least calculator.py and main.py
    
    
    @pytest.mark.asyncio
    async def test_performance_with_large_files(self, temp_project_dir, logger):
        """Test performance with large files."""
        indexer = LSPIndexer(logger)
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
        indexer = LSPIndexer(logger)
        await indexer.initialize(str(temp_project_dir))
        
        # Should not raise errors during shutdown
        indexer.shutdown()
        
        # After shutdown, operations should return empty results
        symbols = await indexer.get_symbols("test.py")
        assert symbols == []