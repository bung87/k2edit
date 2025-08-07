"""
Tests for the AgenticContextManager
"""

import pytest
import asyncio
from pathlib import Path
from src.k2edit.agent.context_manager import AgenticContextManager


class TestAgenticContextManager:
    """Test cases for AgenticContextManager"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, temp_project_dir, logger):
        """Test context manager initialization."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        assert manager.current_context.project_root == str(temp_project_dir)
        assert manager.logger is not None
    
    
    @pytest.mark.asyncio
    async def test_update_context(self, temp_project_dir, sample_python_file, logger):
        """Test updating context with file information."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        # Wait for memory store collections to be initialized
        await asyncio.sleep(0.1)
        while not manager.memory_store.collections:
            await asyncio.sleep(0.01)
        
        await manager.update_context(str(sample_python_file))
        
        assert manager.current_context.file_path == str(sample_python_file)
        assert "sample.py" in str(manager.current_context.file_path)
    
    
    @pytest.mark.asyncio
    async def test_get_enhanced_context(self, temp_project_dir, sample_python_file, logger):
        """Test getting enhanced context for AI processing."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        # Wait for memory store collections to be initialized
        await asyncio.sleep(0.1)
        while not manager.memory_store.collections:
            await asyncio.sleep(0.01)
        
        await manager.update_context(
            str(sample_python_file),
            selected_code="def hello_world():\n    print(\"Hello\")",
            cursor_position={"line": 5, "column": 8}
        )
        
        context = await manager.get_enhanced_context("explain this function")
        
        assert "current_file" in context
        assert "language" in context
        assert "selected_code" in context
        assert context["selected_code"] == "def hello_world():\n    print(\"Hello\")"
    
    
    @pytest.mark.asyncio
    async def test_get_enhanced_context_for_file(self, temp_project_dir, sample_python_file, logger):
        """Test file context extraction."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        context = await manager.get_enhanced_context_for_file(str(sample_python_file))
        
        assert "file_path" in context
        assert "language" in context
        assert "symbols" in context
        assert context["language"] == "python"
        assert context["file_path"] == str(sample_python_file)
    
    
    @pytest.mark.asyncio
    async def test_record_change(self, temp_project_dir, sample_python_file, logger):
        """Test recording code changes."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        # Wait for memory store collections to be initialized
        await asyncio.sleep(0.1)
        while not manager.memory_store.collections:
            await asyncio.sleep(0.01)
        
        await manager.record_change(
            str(sample_python_file),
            "modify",
            "old content",
            "new content"
        )
        
        # Verify change was recorded in current context
        assert len(manager.current_context.recent_changes) > 0
        assert manager.current_context.recent_changes[0]["change_type"] == "modify"
    
    
    @pytest.mark.asyncio
    async def test_get_project_overview(self, temp_project_dir, complex_project, logger):
        """Test getting project-level context."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(complex_project))
        
        context = await manager._get_project_overview()
        
        assert "file_structure" in context
        assert "readme_summary" in context
        assert isinstance(context["file_structure"], dict)
        assert "files" in context["file_structure"]
        assert isinstance(context["file_structure"]["files"], list)
    
    
    @pytest.mark.asyncio
    async def test_process_agent_request(self, temp_project_dir, logger):
        """Test processing agent requests."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        # Wait for memory store collections to be initialized
        await asyncio.sleep(0.1)
        while not manager.memory_store.collections:
            await asyncio.sleep(0.01)
        
        # Create similar files
        file1 = temp_project_dir / "file1.py"
        file1.write_text("def process_data(data):\n    return data.upper()")
        
        file2 = temp_project_dir / "file2.py"
        file2.write_text("def process_text(text):\n    return text.lower()")
        
        result = await manager.process_agent_request("def process_data")
        
        assert "query" in result
        assert "context" in result
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)
    
    
    @pytest.mark.asyncio
    async def test_empty_project(self, temp_project_dir, logger):
        """Test behavior with empty project."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        # Wait for memory store collections to be initialized
        await asyncio.sleep(0.1)
        while not manager.memory_store.collections:
            await asyncio.sleep(0.01)
        
        context = await manager.get_enhanced_context("test query")
        
        assert "project_overview" in context
        assert isinstance(context["project_overview"], dict)
    
    
    @pytest.mark.asyncio
    async def test_nonexistent_file(self, temp_project_dir, logger):
        """Test handling of nonexistent files."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        nonexistent = temp_project_dir / "nonexistent.py"
        
        # Should handle gracefully
        context = await manager.get_enhanced_context_for_file(str(nonexistent))
        assert context["file_path"] == str(nonexistent)
        assert context["language"] == "python"
    
    
    @pytest.mark.asyncio
    async def test_multiple_files(self, temp_project_dir, logger):
        """Test context with multiple files."""
        manager = AgenticContextManager(logger=logger)
        await manager.initialize(str(temp_project_dir))
        
        # Wait for memory store collections to be initialized
        await asyncio.sleep(0.1)
        while not manager.memory_store.collections:
            await asyncio.sleep(0.01)
        
        # Create multiple files
        files = []
        for i in range(3):
            file_path = temp_project_dir / f"test{i}.py"
            file_path.write_text(f"def func{i}():\n    return {i}")
            files.append(str(file_path))
        
        # Update context with first file
        await manager.update_context(files[0])
        context = await manager.get_enhanced_context("test")
        
        assert "project_overview" in context
        assert "current_file" in context
        assert context["current_file"] == files[0]