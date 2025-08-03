"""Agentic Context Manager for K2Edit
Handles AI agent interactions, context management, and orchestration
"""

# Configure multiprocessing FIRST to avoid fork issues on macOS
import os
import multiprocessing
if os.name == 'posix':
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError as e:
        logger.warning(f"Multiprocessing start method already set: {e}")  # Already set

import asyncio
import json
import logging
import re
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from sentence_transformers import SentenceTransformer

from .memory_config import create_memory_store
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
        self.logger = logger or logging.getLogger("k2edit")
        self.memory_store = create_memory_store(self, logger)
        self.lsp_indexer = LSPIndexer(logger)
        self.current_context: Optional[AgentContext] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.embedding_model = None
        self._embedding_lock = None
        
        # Initialize embedding model
        try:
            model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'all-MiniLM-L6-v2')
            # Disable multiprocessing completely to avoid macOS fork issues
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'
            os.environ['OMP_NUM_THREADS'] = '1'
            self.embedding_model = SentenceTransformer(model_path)
            self._embedding_lock = threading.Lock()
            self.logger.info("Successfully loaded local SentenceTransformer model")
        except Exception as e:
            self.logger.error(f"Error loading local SentenceTransformer model: {e}")
            self.embedding_model = None
            self._embedding_lock = None
        
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

    async def add_context_file(self, file_path: str, file_content: str = None):
        """Add a file to the conversation context without changing current context"""
        if not file_content:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {e}")
                return False
        
        # Store the file as additional context
        context_entry = {
            "type": "additional_file",
            "file_path": file_path,
            "content": file_content,
            "language": self._detect_language(file_path),
            "timestamp": datetime.now().isoformat()
        }
        
        # Store in memory store
        await self.memory_store.store_conversation({
            "type": "context_addition",
            "file_path": file_path,
            "content_preview": file_content[:200] + "..." if len(file_content) > 200 else file_content,
            "timestamp": datetime.now().isoformat()
        })
        
        self.logger.info(f"Added file to context: {file_path}")
        return True
        
    async def _analyze_file_structure(self, project_root: str, max_depth: int = 3) -> List[str]:
        """Analyze and return the file structure of the project."""
        structure = []
        root = Path(project_root)
        # Simple ignore list
        ignore_dirs = ['.git', '__pycache__', 'node_modules', '.vscode']
        
        for path in sorted(root.rglob('*')):
            # Skip ignored directories
            if any(part in path.parts for part in ignore_dirs):
                continue

            depth = len(path.relative_to(root).parts)
            if depth > max_depth:
                continue

            indent = '  ' * (depth - 1)
            if path.is_dir():
                structure.append(f"{indent}├── {path.name}/")
            else:
                structure.append(f"{indent}├── {path.name}")
        return structure

    async def _get_project_overview(self) -> Dict[str, Any]:
        """Get a high-level overview of the project."""
        if not self.current_context or not self.current_context.project_root:
            return {}

        project_root = Path(self.current_context.project_root)
        overview = {
            "file_structure": await self._analyze_file_structure(self.current_context.project_root),
            "readme_summary": None
        }

        # Find and summarize README
        readme_files = [p for p in project_root.glob('README*') if p.is_file()]
        if readme_files:
            readme_path = readme_files[0]
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    readme_content = f.read()
                    # Simple summary: first 15 lines
                    overview["readme_summary"] = "\n".join(readme_content.splitlines()[:15])
            except Exception as e:
                self.logger.warning(f"Could not read {readme_path.name}: {e}")
        
        return overview

    async def get_enhanced_context(self, query: str) -> Dict[str, Any]:
        """Get enhanced context for AI agent based on query including semantic search and hierarchical data"""
        if not self.current_context:
            return {}
            
        # Get basic context from the current file
        context = {
            "current_file": self.current_context.file_path,
            "language": self.current_context.language,
            "selected_code": self.current_context.selected_code,
            "cursor_position": self.current_context.cursor_position,
            "symbols": self.current_context.symbols,
            "dependencies": self.current_context.dependencies,
            "recent_changes": self.current_context.recent_changes
        }
        
        # Get LSP-based outline and enhanced context for the current file
        if self.current_context.file_path:
            try:
                line = self.current_context.cursor_position.get('line') if self.current_context.cursor_position else None
                
                lsp_context = await self.lsp_indexer.get_enhanced_context_for_file(
                    self.current_context.file_path, 
                    line
                )
                context.update({
                    "lsp_outline": lsp_context.get("outline", []),
                    "lsp_symbols": lsp_context.get("symbols", []),
                    "lsp_metadata": lsp_context.get("metadata", {}),
                    "line_context": lsp_context.get("line_context")
                })
                
                if lsp_context.get("symbols"):
                    context["symbols"] = lsp_context["symbols"]
                    self.current_context.symbols = lsp_context["symbols"]
                    
            except Exception as e:
                self.logger.error(f"Failed to get LSP context for file: {e}")

        # Always include a project overview for broader context
        context["project_overview"] = await self._get_project_overview()

        # If the query seems general (not focused on specific code), add project-wide context.
        is_general_query = not self.current_context.file_path or not self.current_context.selected_code
        if is_general_query:
            self.logger.info("General query detected, fetching project-wide symbols.")
            project_symbols = await self.lsp_indexer.get_project_symbols()
            context["project_symbols"] = project_symbols

        # Get semantic search results from memory
        semantic_results = await self.memory_store.semantic_search(query)
        context["semantic_context"] = semantic_results
        
        # Get relevant historical context from memory
        relevant_history = await self.memory_store.search_relevant_context(query)
        context["relevant_history"] = relevant_history
        
        # Find similar code patterns if there is a selection
        if self.current_context.selected_code:
            similar_patterns = await self.memory_store.find_similar_code(
                self.current_context.selected_code
            )
            context["similar_patterns"] = similar_patterns
            
        return context
        
    async def _analyze_file_structure(self, project_root: str) -> Dict[str, Any]:
        """Analyze project file structure"""
        import os
        structure = {
            "root": project_root,
            "files": [],
            "directories": [],
            "language_stats": {}
        }
        
        for root, dirs, files in os.walk(project_root):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'dist', 'build', '.git']]
            
            for file in files:
                if not file.startswith('.'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, project_root)
                    
                    # Determine language
                    lang = self._detect_language_from_filename(file)
                    structure["files"].append({
                        "path": rel_path,
                        "language": lang,
                        "size": os.path.getsize(file_path)
                    })
                    
                    structure["language_stats"][lang] = structure["language_stats"].get(lang, 0) + 1
        
        return structure

    def _detect_language_from_filename(self, filename: str) -> str:
        """Detect programming language from filename"""
        import os
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.sql': 'sql',
            '.sh': 'shell',
            '.md': 'markdown'
        }
        
        _, ext = os.path.splitext(filename)
        return ext_map.get(ext.lower(), 'unknown')
        
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

    def _generate_embedding(self, content: str) -> List[float]:
        """Generate semantic embedding for content using SentenceTransformer."""
        if not self.embedding_model:
            self.logger.warning("Embedding model not available, returning zero vector.")
            return [0.0] * 384  # Dimension of all-MiniLM-L6-v2 is 384

        try:
            # Use threading lock to prevent concurrent access issues
            # Disable multiprocessing entirely to avoid macOS fork issues
            if self._embedding_lock:
                with self._embedding_lock:
                    embedding = self.embedding_model.encode(
                        content, 
                        convert_to_tensor=False,
                        show_progress_bar=False,
                        batch_size=1,
                        device='cpu',
                        normalize_embeddings=True,
                        num_workers=0  # Explicitly disable multiprocessing
                    )
            else:
                embedding = self.embedding_model.encode(
                    content, 
                    convert_to_tensor=False,
                    show_progress_bar=False,
                    batch_size=1,
                    device='cpu',
                    normalize_embeddings=True,
                    num_workers=0  # Explicitly disable multiprocessing
                )
            return embedding.tolist()
        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            return [0.0] * 384


# Global context manager instance
_context_manager = None


async def get_context_manager(logger: logging.Logger = None) -> AgenticContextManager:
    """Get or create the global context manager instance"""
    global _context_manager
    if _context_manager is None:
        _context_manager = AgenticContextManager(logger)
    return _context_manager