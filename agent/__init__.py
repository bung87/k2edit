"""
K2Edit Agentic System
Comprehensive solution for agentic context, memory, and LSP indexing
"""

from aiologger import Logger
from typing import Dict, List, Any, Optional

from .context_manager import AgenticContextManager
from .lsp_indexer import LSPIndexer

__all__ = [
    'AgenticContextManager',
    'LSPIndexer',
    'initialize_agentic_system',
    'get_agent_context',
    'process_agent_query'
]


# Global agentic system instance
_agentic_system = None


async def initialize_agentic_system(project_root: str, logger: Logger = None, progress_callback=None):
    """
    Initialize the complete agentic system with progress updates
    
    Args:
        project_root: Path to the project root directory
        logger: Logger instance for debugging
        progress_callback: Async callback function for progress updates
    """
    global _agentic_system
    
    if logger is None:
        logger = Logger(name="k2edit")
    
    if progress_callback:
        await progress_callback("Initializing agentic system...")
    
    # Initialize context manager
    _agentic_system = AgenticContextManager(logger)
    await _agentic_system.initialize(project_root, progress_callback)
    
    if progress_callback:
        await progress_callback("Agentic system initialized")
    
    return _agentic_system


async def get_agent_context() -> Optional[AgenticContextManager]:
    """Get the global agentic system instance"""
    return _agentic_system


async def process_agent_query(query: str, file_path: str = None, 
                            selected_code: str = None, 
                            cursor_position: Dict[str, int] = None) -> Dict[str, Any]:
    """
    Process an agent query with full context
    
    Args:
        query: The user's query to process
        file_path: Current file being edited
        selected_code: Currently selected code
        cursor_position: Current cursor position
        
    Returns:
        Enhanced context dictionary for AI processing
    """
    if _agentic_system is None:
        raise RuntimeError("Agentic system not initialized")
        
    # Update context if file info provided
    if file_path:
        await _agentic_system.update_context(
            file_path, selected_code, cursor_position
        )
        
    # Process the query
    return await _agentic_system.process_agent_request(query)

async def record_code_change(file_path: str, change_type: str, 
                           old_content: str, new_content: str):
    """
    Record a code change in the agentic system
    
    Args:
        file_path: Path to the file that changed
        change_type: Type of change (add, modify, delete)
        old_content: Previous content
        new_content: New content
    """
    if _agentic_system is None:
        return
        
    await _agentic_system.record_change(
        file_path, change_type, old_content, new_content
    )


async def get_code_intelligence(file_path: str) -> Dict[str, Any]:
    """
    Get comprehensive code intelligence for a file
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary containing symbols, dependencies, and other intelligence
    """
    if _agentic_system is None:
        return {}
        
    context = await _agentic_system.get_enhanced_context("code_intelligence")
    
    # Get symbols for specific file
    symbols = await _agentic_system.lsp_indexer.get_symbols(file_path)
    dependencies = await _agentic_system.lsp_indexer.get_dependencies(file_path)
    
    return {
        "symbols": symbols,
        "dependencies": dependencies,
        "file_info": _agentic_system.lsp_indexer.get_file_info(file_path),
        "cross_references": await _get_cross_references(symbols)
    }


async def _get_cross_references(symbols: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Get cross-references for symbols"""
    if _agentic_system is None:
        return {}
        
    references = {}
    
    for symbol in symbols:
        symbol_name = symbol.get("name")
        if symbol_name:
            refs = await _agentic_system.lsp_indexer.find_symbol_references(symbol_name)
            references[symbol_name] = [
                f"{ref['file_path']}:{ref['line']}"
                for ref in refs
            ]
            
    return references


# Utility functions
async def shutdown_agentic_system():
    """Shutdown the agentic system and cleanup resources"""
    global _agentic_system
    
    if _agentic_system:
        if hasattr(_agentic_system, 'lsp_indexer'):
            await _agentic_system.lsp_indexer.shutdown()
        _agentic_system = None


# Configuration
DEFAULT_AGENT_CONFIG = {
    "memory_retention_days": 30,
    "max_conversation_history": 100,
    "enable_lsp_indexing": True,
    "symbol_refresh_interval": 300,  # seconds
    "similarity_threshold": 0.7
}