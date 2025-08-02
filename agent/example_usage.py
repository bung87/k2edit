"""
Example usage of the K2Edit Agentic System
Demonstrates how to integrate agentic context, memory, and LSP indexing
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import initialize_agentic_system, process_agent_query, record_code_change


async def main():
    """Demonstrate the agentic system capabilities"""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("k2edit.agent.example")
    
    # Initialize the agentic system
    project_root = Path(__file__).parent.parent
    logger.info(f"Initializing agentic system for {project_root}")
    
    try:
        # Initialize the complete system
        agent_system = await initialize_agentic_system(str(project_root), logger)
        
        # Example 1: Process a code completion query
        logger.info("\n=== Example 1: Code Completion ===")
        completion_result = await process_agent_query(
            query="suggest improvements for this function",
            file_path="main.py",
            selected_code="def compose(self) -> ComposeResult:",
            cursor_position={"line": 140, "column": 0}
        )
        
        print("Query:", completion_result["query"])
        print("Suggestions:", completion_result["suggestions"])
        print("Related files:", completion_result["related_files"])
        
        # Example 2: Get code intelligence
        logger.info("\n=== Example 2: Code Intelligence ===")
        intelligence = await get_code_intelligence("main.py")
        
        print("Symbols found:", len(intelligence.get("symbols", [])))
        print("Dependencies:", intelligence.get("dependencies", []))
        print("File info:", intelligence.get("file_info"))
        
        # Example 3: Record a code change
        logger.info("\n=== Example 3: Recording Change ===")
        await record_code_change(
            file_path="example.py",
            change_type="modify",
            old_content="def old_function():\n    pass",
            new_content="def improved_function():\n    return True"
        )
        
        logger.info("Change recorded successfully")
        
        # Example 4: Process error fixing query
        logger.info("\n=== Example 4: Error Analysis ===")
        error_result = await process_agent_query(
            query="fix this NameError: name 'Message' is not defined",
            file_path="views/file_explorer.py",
            selected_code="class FileSelected(Message):"
        )
        
        print("Error analysis suggestions:", error_result["suggestions"])
        
        # Example 5: Memory search
        logger.info("\n=== Example 5: Memory Search ===")
        from agent.memory_store import MemoryStore
        
        memory_store = MemoryStore(logger)
        await memory_store.initialize(str(project_root))
        
        recent_conversations = await memory_store.get_recent_conversations(5)
        print("Recent conversations:", len(recent_conversations))
        
        # Example 6: Symbol navigation
        logger.info("\n=== Example 6: Symbol Navigation ===")
        from agent.lsp_indexer import LSPIndexer
        
        lsp_indexer = LSPIndexer(logger)
        await lsp_indexer.initialize(str(project_root))
        
        symbols = await lsp_indexer.get_symbols("main.py")
        print("Symbols in main.py:", len(symbols))
        
        # Find references
        if symbols:
            symbol_name = symbols[0]["name"] if symbols else "compose"
            references = await lsp_indexer.find_symbol_references(symbol_name)
            print(f"References to '{symbol_name}':", len(references))
            
        logger.info("\n=== All examples completed successfully ===")
        
    except Exception as e:
        logger.error(f"Error in example usage: {e}", exc_info=True)
        raise
    
    finally:
        # Cleanup
        from agent import shutdown_agentic_system
        await shutdown_agentic_system()
        logger.info("Agentic system shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())