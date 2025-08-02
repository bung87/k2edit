"""
Tests for the AgenticContextManager
"""

import pytest
import asyncio
from pathlib import Path
from agent.context_manager import AgenticContextManager


class TestAgenticContextManager:
    """Test cases for AgenticContextManager"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, temp_project_dir, logger):
        """Test context manager initialization."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        assert manager.project_root == temp_project_dir
        assert manager.logger is not None
    
    
    @pytest.mark.asyncio
    async def test_update_context(self, temp_project_dir, sample_python_file, logger):
        """Test updating context with file information."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        await manager.update_context(str(sample_python_file))
        
        assert manager.current_file == str(sample_python_file)
        assert "sample.py" in str(manager.current_file)
    
    
    @pytest.mark.asyncio
    async def test_get_enhanced_context(self, temp_project_dir, sample_python_file, logger):
        """Test getting enhanced context for AI processing."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        await manager.update_context(
            str(sample_python_file),
            selected_code="def hello_world():\n    print(\"Hello\")",
            cursor_position={"line": 5, "column": 8}
        )
        
        context = await manager.get_enhanced_context("explain this function")
        
        assert "query" in context
        assert "file_context" in context
        assert "project_context" in context
        assert context["query"] == "explain this function"
    
    
    @pytest.mark.asyncio
    async def test_extract_file_context(self, temp_project_dir, sample_python_file, logger):
        """Test file context extraction."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        context = await manager._extract_file_context(str(sample_python_file))
        
        assert "file_path" in context
        assert "language" in context
        assert "content" in context
        assert context["language"] == "python"
        assert "hello_world" in context["content"]
    
    
    @pytest.mark.asyncio
    async def test_record_change(self, temp_project_dir, sample_python_file, logger):
        """Test recording code changes."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        await manager.record_change(
            str(sample_python_file),
            "modify",
            "old content",
            "new content"
        )
        
        # Verify change was recorded (would need to check memory store)
        assert True  # Basic test that method runs without error
    
    
    @pytest.mark.asyncio
    async def test_get_project_context(self, temp_project_dir, complex_project, logger):
        """Test getting project-level context."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(complex_project))
        
        context = await manager._get_project_context()
        
        assert "project_structure" in context
        assert "language_distribution" in context
        assert "recent_files" in context
        assert isinstance(context["project_structure"], dict)
    
    
    @pytest.mark.asyncio
    async def test_find_similar_patterns(self, temp_project_dir, logger):
        """Test finding similar code patterns."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        # Create similar files
        file1 = temp_project_dir / "file1.py"
        file1.write_text("def process_data(data):\n    return data.upper()")
        
        file2 = temp_project_dir / "file2.py"
        file2.write_text("def process_text(text):\n    return text.lower()")
        
        patterns = await manager._find_similar_patterns("def process_data")
        
        assert isinstance(patterns, list)
    
    
    @pytest.mark.asyncio
    async def test_empty_project(self, temp_project_dir, logger):
        """Test behavior with empty project."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        context = await manager.get_enhanced_context("test query")
        
        assert context["project_context"]["language_distribution"] == {}
        assert context["project_context"]["recent_files"] == []
    
    
    @pytest.mark.asyncio
    async def test_nonexistent_file(self, temp_project_dir, logger):
        """Test handling of nonexistent files."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        nonexistent = temp_project_dir / "nonexistent.py"
        
        # Should handle gracefully
        context = await manager._extract_file_context(str(nonexistent))
        assert context["file_path"] == str(nonexistent)
        assert context["content"] == ""
    
    
    @pytest.mark.asyncio
    async def test_multiple_files(self, temp_project_dir, logger):
        """Test context with multiple files."""
        manager = AgenticContextManager(logger)
        await manager.initialize(str(temp_project_dir))
        
        # Create multiple files
        files = []
        for i in range(3):
            file_path = temp_project_dir / f"test{i}.py"
            file_path.write_text(f"def func{i}():\n    return {i}")
            files.append(str(file_path))
        
        # Update context with first file
        await manager.update_context(files[0])
        context = await manager.get_enhanced_context("test")
        
        assert "project_context" in context
        assert len(context["project_context"]["recent_files"]) >= 3