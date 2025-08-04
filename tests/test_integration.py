"""
Integration tests for the complete agentic system
"""

import pytest
import asyncio
from pathlib import Path
from k2edit.agent import initialize_agentic_system, process_agent_query, record_code_change, get_code_intelligence
from k2edit.agent.integration import K2EditAgentIntegration


class TestIntegration:
    """Integration tests for the complete agentic system"""
    
    @pytest.mark.asyncio
    async def test_full_system_initialization(self, temp_project_dir, logger):
        """Test complete system initialization."""
        agent = await initialize_agentic_system(str(temp_project_dir), logger)
        assert agent is not None
        
        # Verify all components are initialized
        assert hasattr(agent, 'memory_store')
        assert hasattr(agent, 'lsp_indexer')
        assert agent.project_root == temp_project_dir
    
    
    @pytest.mark.asyncio
    async def test_end_to_end_query_processing(self, temp_project_dir, sample_python_file, logger):
        """Test complete query processing pipeline."""
        await initialize_agentic_system(str(temp_project_dir), logger)
        
        result = await process_agent_query(
            query="What functions are in this file?",
            file_path=str(sample_python_file),
            selected_code="def hello_world():\n    print('Hello')",
            cursor_position={"line": 1, "column": 0}
        )
        
        assert isinstance(result, dict)
        assert "query" in result
        assert "context" in result
        assert "suggestions" in result
        assert "related_files" in result
        assert result["query"] == "What functions are in this file?"
    
    
    @pytest.mark.asyncio
    async def test_code_change_tracking(self, temp_project_dir, logger):
        """Test complete code change tracking pipeline."""
        await initialize_agentic_system(str(temp_project_dir), logger)
        
        test_file = temp_project_dir / "test_change.py"
        test_file.write_text("def original():\n    return False")
        
        old_content = test_file.read_text()
        new_content = "def improved():\n    return True"
        
        await record_code_change(
            file_path=str(test_file),
            change_type="modify",
            old_content=old_content,
            new_content=new_content
        )
        
        # Verify change was recorded in memory
        from k2edit.agent import get_agent_context
        agent = await get_agent_context()
        if agent:
            changes = await agent.memory_store.search_memory("test_change.py")
            assert len(changes) > 0
    
    
    @pytest.mark.asyncio
    async def test_code_intelligence_pipeline(self, temp_project_dir, complex_project, logger):
        """Test complete code intelligence pipeline."""
        await initialize_agentic_system(str(complex_project), logger)
        
        main_file = complex_project / "main.py"
        intelligence = await get_code_intelligence(str(main_file))
        
        assert isinstance(intelligence, dict)
        assert "symbols" in intelligence
        assert "dependencies" in intelligence
        assert "file_info" in intelligence
        assert "cross_references" in intelligence
        
        # Should find symbols in the file
        assert len(intelligence["symbols"]) > 0
        
        # Should find dependencies
        assert len(intelligence["dependencies"]) > 0
    
    
    @pytest.mark.asyncio
    async def test_k2edit_integration_class(self, temp_project_dir, logger):
        """Test the K2Edit integration class."""
        integration = K2EditAgentIntegration(str(temp_project_dir))
        await integration.initialize()
        
        assert integration.agent_initialized is True
        
        # Test file open
        test_file = temp_project_dir / "integration_test.py"
        test_file.write_text("print('test')")
        await integration.on_file_open(str(test_file))
        
        # Test file change
        await integration.on_file_change(
            str(test_file),
            old_content="print('test')",
            new_content="print('updated')"
        )
        
        # Test AI query
        result = await integration.on_ai_query(
            query="explain this print statement",
            file_path=str(test_file)
        )
        
        assert isinstance(result, dict)
        assert "context" in result
        
        await integration.shutdown()
    
    
    @pytest.mark.asyncio
    async def test_context_memory_lsp_integration(self, temp_project_dir, logger):
        """Test integration between context, memory, and LSP components."""
        await initialize_agentic_system(str(temp_project_dir), logger)
        
        # Create a test file
        test_file = temp_project_dir / "integration_test.py"
        test_file.write_text('''
def calculate_sum(a, b):
    return a + b

def calculate_product(a, b):
    return a * b

class MathProcessor:
    def __init__(self):
        self.results = []
    
    def process(self, a, b):
        sum_result = calculate_sum(a, b)
        product_result = calculate_product(a, b)
        self.results.append((sum_result, product_result))
        return sum_result, product_result
''')
        
        # Process a query that uses all components
        result = await process_agent_query(
            query="How can I optimize this MathProcessor class?",
            file_path=str(test_file),
            selected_code="def process(self, a, b):\n    sum_result = calculate_sum(a, b)",
            cursor_position={"line": 10, "column": 4}
        )
        
        # Verify all components contributed
        context = result["context"]
        assert "file_context" in context
        assert "project_context" in context
        assert "symbols" in context
        assert "dependencies" in context
        
        # Should have suggestions from LSP analysis
        assert len(result["suggestions"]) > 0
    
    
    @pytest.mark.asyncio
    async def test_memory_context_consistency(self, temp_project_dir, logger):
        """Test consistency between memory and context updates."""
        await initialize_agentic_system(str(temp_project_dir), logger)
        
        test_file = temp_project_dir / "consistency_test.py"
        original_content = "def original_func():\n    return 1"
        test_file.write_text(original_content)
        
        # Update context
        from k2edit.agent import get_agent_context
        agent = await get_agent_context()
        await agent.update_context(str(test_file))
        
        # Make a change
        new_content = "def improved_func():\n    return 42"
        await record_code_change(
            file_path=str(test_file),
            change_type="modify",
            old_content=original_content,
            new_content=new_content
        )
        
        # Verify memory and context are consistent
        memory_entries = await agent.memory_store.search_memory("consistency_test.py")
        assert len(memory_entries) > 0
        
        # Should be able to query about the change
        result = await process_agent_query(
            query="What changed in this file?",
            file_path=str(test_file)
        )
        
        assert "context" in result
    
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, temp_project_dir, logger):
        """Test error handling across the integrated system."""
        await initialize_agentic_system(str(temp_project_dir), logger)
        
        # Test with nonexistent file
        result = await process_agent_query(
            query="analyze this file",
            file_path="nonexistent.py"
        )
        
        # Should handle gracefully
        assert isinstance(result, dict)
        assert "context" in result
        
        # Test with invalid change
        await record_code_change(
            file_path="invalid/file.py",
            change_type="invalid_type",
            old_content="",
            new_content=""
        )
        
        # Should not crash the system
        assert True  # Test passes if no exception
    
    
    @pytest.mark.asyncio
    async def test_performance_integration(self, temp_project_dir, logger):
        """Test performance of the integrated system."""
        import time
        
        await initialize_agentic_system(str(temp_project_dir), logger)
        
        # Create multiple files
        for i in range(10):
            file_path = temp_project_dir / f"test_{i}.py"
            file_path.write_text(f"""
def function_{i}():
    return {i}

class Class_{i}:
    def method_{i}(self):
        return {i}
""")
        
        # Measure time for processing queries
        start_time = time.time()
        
        for i in range(5):
            result = await process_agent_query(
                query=f"analyze file {i}",
                file_path=str(temp_project_dir / f"test_{i}.py")
            )
            assert "context" in result
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert processing_time < 10.0  # 10 seconds for 5 queries
    
    
    @pytest.mark.asyncio
    async def test_project_wide_analysis(self, temp_project_dir, complex_project, logger):
        """Test project-wide analysis capabilities."""
        await initialize_agentic_system(str(complex_project), logger)
        
        # Test querying about project structure
        result = await process_agent_query(
            query="What classes are available in this project?",
            file_path=str(complex_project / "main.py")
        )
        
        assert "Calculator" in str(result["context"])
        assert len(result["related_files"]) > 0
    
    
    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self, temp_project_dir, logger):
        """Test proper cleanup on system shutdown."""
        agent = await initialize_agentic_system(str(temp_project_dir), logger)
        
        # Perform some operations
        test_file = temp_project_dir / "shutdown_test.py"
        test_file.write_text("print('test')")
        
        await process_agent_query("test", str(test_file))
        await record_code_change(str(test_file), "add", "", "print('test')")
        
        # Shutdown
        from k2edit.agent import shutdown_agentic_system
        await shutdown_agentic_system()
        
        # Verify system is properly shutdown
        from k2edit.agent import get_agent_context
        agent = await get_agent_context()
        assert agent is None

    @pytest.mark.asyncio
    async def test_agent_context_extraction_for_kimi_api(self, temp_project_dir, logger):
        """Test that agentic system context is properly extracted for Kimi API."""
        await initialize_agentic_system(str(temp_project_dir), logger)
        
        # Create a test file
        test_file = temp_project_dir / "context_extraction_test.py"
        test_file.write_text('''
def process_data(data):
    """Process input data"""
    return [item * 2 for item in data]

class DataProcessor:
    def __init__(self):
        self.cache = {}
    
    def process(self, data):
        if str(data) in self.cache:
            return self.cache[str(data)]
        result = process_data(data)
        self.cache[str(data)] = result
        return result
''')
        
        # Test agentic system integration
        integration = K2EditAgentIntegration(str(temp_project_dir))
        await integration.initialize()
        
        # Simulate the context extraction that happens in command_bar.py
        agent_result = await integration.on_ai_query(
            query="review this code for optimization opportunities",
            file_path=str(test_file),
            selected_text="def process(self, data):\n    if str(data) in self.cache:",
            cursor_position={"line": 10, "column": 8}
        )
        
        # Verify the structure matches what command_bar.py expects
        assert isinstance(agent_result, dict)
        assert "context" in agent_result
        assert "suggestions" in agent_result
        assert "related_files" in agent_result
        
        # Extract context like command_bar.py does
        context = agent_result.get("context", {})
        
        # Verify context has agentic system data
        assert isinstance(context, dict)
        
        # Should have enhanced context from agentic system
        has_agent_context = any(key in context for key in [
            "project_symbols", "semantic_context", "relevant_history", 
            "similar_patterns", "file_context", "project_context"
        ])
        assert has_agent_context, f"Expected agentic context keys, got: {list(context.keys())}"
        
        # Should NOT have the wrapper structure
        assert "suggestions" not in context
        assert "related_files" not in context
        
        await integration.shutdown()