#!/usr/bin/env python3
"""
Tests for the agent tools functionality, specifically the analyze_code method
and its integration with LSP-based and regex-based analysis.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Import the tools class
from src.k2edit.agent.tools import ToolExecutor
from src.k2edit.logger import Logger


class TestAgentTools:
    """Test cases for ToolExecutor analyze_code functionality"""
    
    @pytest.fixture
    def agent_tools(self, logger):
        """Create a ToolExecutor instance for testing."""
        tools = ToolExecutor(logger=logger)
        return tools
    
    @pytest.fixture
    def logger(self):
        """Create a mock logger for testing."""
        logger = AsyncMock()
        return logger
    
    @pytest.fixture
    def sample_python_code(self):
        """Sample Python code for testing analysis."""
        return '''
import os
import subprocess
from typing import List, Dict

class Calculator:
    """A simple calculator class."""
    
    def __init__(self):
        self.history = []
        self.secret_key = "hardcoded_secret_123456789"
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        result = a + b
        self.history.append(f"add({a}, {b}) = {result}")
        return result
    
    def execute_command(self, cmd: str):
        """Execute a system command - potential security issue."""
        return os.system(cmd)
    
    def dangerous_eval(self, expression: str):
        """Evaluate expression - security risk."""
        return eval(expression)
    
    def complex_calculation(self, data: List[int]) -> Dict[str, Any]:
        """Complex calculation with nested loops."""
        results = {}
        for i in range(len(data)):
            for j in range(len(data)):
                if i != j:
                    try:
                        results[f"{i}_{j}"] = data[i] / data[j]
                    except ZeroDivisionError:
                        results[f"{i}_{j}"] = None
        return results

def main():
    calc = Calculator()
    print(calc.add(5, 3))
    
    # Long line that exceeds 100 characters - this is a very long comment that should trigger a style warning
    calc.execute_command("ls -la")
'''
    
    @pytest.fixture
    def temp_python_file(self, tmp_path, sample_python_code):
        """Create a temporary Python file for testing."""
        test_file = tmp_path / "test_code.py"
        test_file.write_text(sample_python_code)
        return str(test_file)
    

    
    @pytest.mark.asyncio
    async def test_analyze_code_lsp_only(self, agent_tools, sample_python_code, temp_python_file):
        """Test that analyze_code only uses LSP-based analysis."""
        # Mock editor to provide content
        mock_editor = Mock()
        mock_editor.get_selected_text.return_value = None
        mock_editor.text = sample_python_code
        mock_editor.current_file = temp_python_file
        agent_tools.editor = mock_editor
        
        # Test that analyze_code returns error when LSP is not available
        result = await agent_tools.analyze_code("structure", "file")
        
        assert "error" in result
        assert "LSP-based analysis not available" in result["error"]
        assert "Please ensure LSP server is running" in result["error"]
    
    @pytest.mark.asyncio
    async def test_analyze_code_error_handling(self, agent_tools):
        """Test error handling when no content is available."""
        agent_tools.editor = None
        
        result = await agent_tools.analyze_code("structure", "file")
        
        assert "error" in result
        assert "No content available" in result["error"]
    
    @pytest.mark.asyncio
    async def test_lsp_analysis_unavailable(self, agent_tools, sample_python_code):
        """Test that _get_lsp_analysis returns None when LSP is not available."""
        # Test that _get_lsp_analysis returns None when LSP is not available
        result = await agent_tools._get_lsp_analysis("structure", "test.py", sample_python_code)
        
        # Should return None since LSP components are not actually available
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])