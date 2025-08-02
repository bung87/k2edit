"""
Agentic Context Manager for K2Edit
Handles AI agent interactions, context management, and orchestration
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from .memory_store import MemoryStore
from .lsp_indexer import LSPIndexer


@dataclass
class AgentContext:
    """Represents the current context for AI agent operations"""
    file_path: Optional[str] = None
    selected_code: Optional[str] = None
    cursor_position: Optional[Dict[str, int]] = None
    project_root: Optional[str] = None
    language: Optional[str] = None
    dependencies: List[str] = None
    symbols: List[Dict[str, Any]] = None
    recent_changes: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.symbols is None:
            self.symbols = []
        if self.recent_changes is None:
            self.recent_changes = []


class AgenticContextManager:
    """Manages AI agent context, memory, and LSP integration"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self.memory_store = MemoryStore(logger)
        self.lsp_indexer = LSPIndexer(logger)
        self.current_context: Optional[AgentContext] = None
        self.conversation_history: List[Dict[str, Any]] = []
        
    async def initialize(self, project_root: str):
        """Initialize the context manager with project root"""
        self.logger.info(f"Initializing agentic context manager for {project_root}")
        
        # Initialize memory store
        await self.memory_store.initialize(project_root)
        
        # Initialize LSP indexer
        await self.lsp_indexer.initialize(project_root)
        
        # Set initial context
        self.current_context = AgentContext(
            project_root=project_root,
            language=self._detect_language(project_root)
        )
        
    async def update_context(self, file_path: str, selected_code: str = None, 
                           cursor_position: Dict[str, int] = None):
        """Update the current context based on editor state"""
        if not self.current_context:
            return
            
        self.current_context.file_path = file_path
        self.current_context.selected_code = selected_code
        self.current_context.cursor_position = cursor_position
        
        # Update symbols from LSP
        symbols = await self.lsp_indexer.get_symbols(file_path)
        self.current_context.symbols = symbols
        
        # Update dependencies
        dependencies = await self.lsp_indexer.get_dependencies(file_path)
        self.current_context.dependencies = dependencies
        
        # Store context in memory
        await self.memory_store.store_context(file_path, asdict(self.current_context))
        
    async def get_enhanced_context(self, query: str) -> Dict[str, Any]:
        """Get enhanced context for AI agent based on query"""
        if not self.current_context:
            return {}
            
        context = {
            "current_file": self.current_context.file_path,
            "language": self.current_context.language,
            "selected_code": self.current_context.selected_code,
            "cursor_position": self.current_context.cursor_position,
            "symbols": self.current_context.symbols,
            "dependencies": self.current_context.dependencies,
            "recent_changes": self.current_context.recent_changes
        }
        
        # Add relevant historical context
        relevant_history = await self.memory_store.search_relevant_context(query)
        context["relevant_history"] = relevant_history
        
        # Add similar code patterns
        similar_patterns = await self.memory_store.find_similar_code(
            self.current_context.selected_code or ""
        )
        context["similar_patterns"] = similar_patterns
        
        # Add project-wide symbols if needed
        if "project" in query.lower() or "global" in query.lower():
            project_symbols = await self.lsp_indexer.get_project_symbols()
            context["project_symbols"] = project_symbols
            
        return context
        
    async def process_agent_request(self, query: str, user_input: str) -> Dict[str, Any]:
        """Process an AI agent request with full context"""
        enhanced_context = await self.get_enhanced_context(query)
        
        # Store conversation
        conversation_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "user_input": user_input,
            "context": enhanced_context
        }
        
        await self.memory_store.store_conversation(conversation_entry)
        self.conversation_history.append(conversation_entry)
        
        return enhanced_context
        
    async def record_change(self, file_path: str, change_type: str, 
                          old_content: str, new_content: str):
        """Record a code change for context tracking"""
        if self.current_context:
            change_entry = {
                "timestamp": datetime.now().isoformat(),
                "file_path": file_path,
                "change_type": change_type,
                "old_content": old_content,
                "new_content": new_content,
                "diff": self._generate_diff(old_content, new_content)
            }
            
            self.current_context.recent_changes.append(change_entry)
            
            # Keep only last 50 changes
            if len(self.current_context.recent_changes) > 50:
                self.current_context.recent_changes = self.current_context.recent_changes[-50:]
                
            await self.memory_store.store_change(change_entry)
            
    def _detect_language(self, project_root: str) -> str:
        """Detect the primary language of the project"""
        root = Path(project_root)
        
        # Common language indicators
        language_indicators = {
            "python": ["requirements.txt", "setup.py", "pyproject.toml", ".py"],
            "javascript": ["package.json", "yarn.lock", ".js", ".ts"],
            "go": ["go.mod", "go.sum", ".go"],
            "rust": ["Cargo.toml", "Cargo.lock", ".rs"],
            "java": ["pom.xml", "build.gradle", ".java"],
            "cpp": ["CMakeLists.txt", "Makefile", ".cpp", ".h"],
            "nim": ["nim.cfg", ".nim", ".nims"]
        }
        
        for lang, indicators in language_indicators.items():
            for indicator in indicators:
                if any(root.rglob(f"*{indicator}")):
                    return lang
                    
        return "unknown"
        
    def _generate_diff(self, old_content: str, new_content: str) -> str:
        """Generate a simple diff between old and new content"""
        import difflib
        return '\n'.join(difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            lineterm=''
        ))


# Global context manager instance
_context_manager = None


async def get_context_manager(logger: logging.Logger = None) -> AgenticContextManager:
    """Get or create the global context manager instance"""
    global _context_manager
    if _context_manager is None:
        _context_manager = AgenticContextManager(logger)
    return _context_manager