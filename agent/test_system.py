"""
Test suite for K2Edit Agentic System

Quick tests to verify the agentic system is working correctly.
"""

import asyncio
import tempfile
import os
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import initialize_agentic_system, shutdown_agentic_system
from agent.context_manager import AgenticContextManager
from agent.memory_store import MemoryStore
from agent.lsp_indexer import LSPIndexer


async def test_context_manager():
    """Test the context manager"""
    print("Testing Context Manager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test file
        test_file = Path(temp_dir) / "test.py"
        test_file.write_text("""
def hello_world():
    print("Hello, World!")
    return True

class TestClass:
    def __init__(self):
        self.value = 42
        
    def get_value(self):
        return self.value
""")
        
        # Test context manager
        manager = AgenticContextManager()
        await manager.initialize(temp_dir)
        
        # Test context update
        await manager.update_context(str(test_file))
        context = await manager.get_enhanced_context("test query")
        
        assert "file_context" in context
        assert "project_context" in context
        print("✓ Context manager test passed")


async def test_memory_store():
    """Test the memory store"""
    print("Testing Memory Store...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        memory = MemoryStore()
        await memory.initialize(temp_dir)
        
        # Test storing conversation
        await memory.store_conversation(
            query="test query",
            response="test response",
            context={"file": "test.py"}
        )
        
        # Test retrieving conversations
        conversations = await memory.get_recent_conversations(1)
        assert len(conversations) > 0
        assert conversations[0]["query"] == "test query"
        
        # Test storing code change
        await memory.store_code_change(
            file_path="test.py",
            change_type="modify",
            old_content="old",
            new_content="new"
        )
        
        print("✓ Memory store test passed")


async def test_lsp_indexer():
    """Test the LSP indexer"""
    print("Testing LSP Indexer...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test Python file
        test_file = Path(temp_dir) / "test_module.py"
        test_file.write_text("""
def calculate_sum(a, b):
    return a + b

class Calculator:
    def __init__(self):
        self.total = 0
    
    def add(self, value):
        self.total += value
        return self.total
""")
        
        indexer = LSPIndexer()
        await indexer.initialize(temp_dir)
        
        # Test symbol extraction
        symbols = await indexer.get_symbols(str(test_file))
        assert len(symbols) > 0
        
        # Test symbol names
        symbol_names = [s["name"] for s in symbols]
        assert "calculate_sum" in symbol_names or "Calculator" in symbol_names
        
        print("✓ LSP indexer test passed")


async def test_full_system():
    """Test the complete agentic system"""
    print("Testing Full System...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test project structure
        (Path(temp_dir) / "src").mkdir()
        main_file = Path(temp_dir) / "src" / "main.py"
        main_file.write_text("""
def main():
    print("Main function")

if __name__ == "__main__":
    main()
""")
        
        # Initialize full system
        agent = await initialize_agentic_system(temp_dir)
        assert agent is not None
        
        # Test query processing
        from agent import process_agent_query
        result = await process_agent_query(
            query="What functions are in this file?",
            file_path=str(main_file)
        )
        
        assert "context" in result
        assert "suggestions" in result
        
        # Test recording changes
        await record_code_change(
            file_path=str(main_file),
            change_type="modify",
            old_content="def main():\n    print(\"Main function\")",
            new_content="def main():\n    print(\"Updated main function\")"
        )
        
        print("✓ Full system test passed")


async def test_integration():
    """Test the integration module"""
    print("Testing Integration...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        from agent.integration import setup_k2edit_agent
        
        agent = await setup_k2edit_agent(temp_dir)
        assert agent is not None
        
        # Test file operations
        test_file = Path(temp_dir) / "test.py"
        test_file.write_text("print('hello')")
        
        await agent.on_file_open(str(test_file))
        await agent.on_file_change(
            str(test_file),
            old_content="print('hello')",
            new_content="print('hello world')"
        )
        
        # Test AI query
        result = await agent.on_ai_query(
            query="explain this code",
            file_path=str(test_file)
        )
        
        assert isinstance(result, dict)
        
        await agent.shutdown()
        print("✓ Integration test passed")


async def run_all_tests():
    """Run all tests"""
    print("🧪 Running K2Edit Agentic System Tests...\n")
    
    try:
        await test_context_manager()
        await test_memory_store()
        await test_lsp_indexer()
        await test_full_system()
        await test_integration()
        
        print("\n🎉 All tests passed successfully!")
        print("\nThe agentic system is ready for use.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    if not success:
        sys.exit(1)