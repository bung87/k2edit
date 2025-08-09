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
        pass  # Already set

import asyncio
import json
import re
import threading
import time
from aiologger import Logger
from aiologger.levels import LogLevel
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from sentence_transformers import SentenceTransformer

from .memory_config import create_memory_store
from .lsp_indexer import LSPIndexer
from ..utils.language_utils import detect_language_from_filename, detect_project_language, detect_language_by_extension


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
    
    def __init__(self, lsp_client=None, logger: Logger = None):
        if logger is None:
            self.logger = Logger.with_default_handlers(name="k2edit")
        else:
            self.logger = logger
        self.memory_store = create_memory_store(self, self.logger)
        self.lsp_indexer = LSPIndexer(lsp_client=lsp_client, logger=self.logger)
        self.current_context: Optional[AgentContext] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.embedding_model = None
        self._embedding_lock = None
        
    async def initialize(self, project_root: str, progress_callback=None):
        """Initialize the context manager with project root and progress updates"""
        
        if progress_callback:
            await progress_callback("Initializing memory store...")
        
        # Initialize memory store and embedding model in the background
        asyncio.create_task(self.memory_store.initialize(project_root))
        asyncio.create_task(self._initialize_embedding_model())

        
        if progress_callback:
            await progress_callback("Starting symbol indexing...")
        
        # Initialize LSP indexer
        try:
            await self.lsp_indexer.initialize(project_root, progress_callback)
        except Exception as e:
            await self.logger.error(f"Failed to initialize LSP indexer: {e}", exc_info=True)
            if progress_callback:
                await progress_callback(f"Error: LSP indexer failed to initialize: {e}")
        
        if progress_callback:
            await progress_callback("LSP indexing started in background...")
        
        # Set initial context
        self.current_context = AgentContext(
            project_root=project_root,
            language=self._detect_language(project_root)
        )
        
        if progress_callback:
            await progress_callback("Agentic system ready")
        
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
                await self.logger.error(f"Error reading file {file_path}: {e}")
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
        
        await self.logger.info(f"Added file to context: {file_path}")
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
                await self.logger.warning(f"Could not read {readme_path.name}: {e}")
        
        return overview

    async def get_enhanced_context(self, query: str, max_semantic_distance: float = 1.2) -> Dict[str, Any]:
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
        
        # Get LSP-based enhanced context for the current file (excluding outline)
        if self.current_context.file_path:
            try:
                line = self.current_context.cursor_position.get('line') if self.current_context.cursor_position else None
                
                lsp_context = await self.get_enhanced_context_for_file(
                    self.current_context.file_path, 
                    line
                )
                context.update({
                    "lsp_symbols": lsp_context.get("symbols", []),
                    "lsp_dependencies": lsp_context.get("dependencies", []),
                    "lsp_metadata": {
                        "language": lsp_context.get("language"),
                        "project_root": lsp_context.get("project_root")
                    }
                })
                
                if lsp_context.get("symbols"):
                    context["symbols"] = lsp_context["symbols"]
                    self.current_context.symbols = lsp_context["symbols"]
                    
            except Exception as e:
                await self.logger.error(f"Failed to get LSP context for file: {e}")

        # Always include a project overview for broader context
        context["project_overview"] = await self._get_project_overview()

        # Only include project-wide symbols when there's no specific file context
        is_general_query = not self.current_context.file_path
        if is_general_query:
            await self.logger.info("General query detected, initiating project-wide symbol collection...")
            await self.logger.info("Query context: {} file_path, {} selected code".format(
                "No" if not self.current_context.file_path else "Has",
                "No" if not self.current_context.selected_code else "Has"
            ))
            
            start_time = time.time()
            project_symbols = await self.lsp_indexer.get_project_symbols(top_level_only=True)
            elapsed_time = time.time() - start_time
            
            await self.logger.info(f"Completed project-wide symbol collection in {elapsed_time:.2f}s")
            await self.logger.info(f"Adding {len(project_symbols)} top-level project symbols to context")
            
            # Log sample of symbols for debugging
            if project_symbols:
                sample_symbols = project_symbols[:5]
                await self.logger.info("Sample project symbols:")
                for symbol in sample_symbols:
                    await self.logger.info(f"  - {symbol.get('name', 'unnamed')} ({symbol.get('kind', 'unknown')}) in {symbol.get('file_path', 'unknown')})")
            
            context["project_symbols"] = project_symbols

        # Get targeted semantic search results from memory with distance filtering
        # Only include high-relevance historical context and conversations
        semantic_results = await self.memory_store.semantic_search(query, limit=5, max_distance=max_semantic_distance)
        
        # Only add semantic context if we have high-quality, relevant results
        if semantic_results and len(semantic_results) > 0:
            context["semantic_context"] = semantic_results
        else:
            context["semantic_context"] = []
        
        # Get relevant historical context from memory with distance filtering
        relevant_history = await self.memory_store.search_relevant_context(query, max_distance=max_semantic_distance)
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
        return detect_language_from_filename(filename)
        
    async def process_agent_request(self, query: str, max_semantic_distance: float = 1.2) -> Dict[str, Any]:
        """Process an AI agent request with full context"""
        enhanced_context = await self.get_enhanced_context(query, max_semantic_distance=max_semantic_distance)
        
        # Store conversation
        conversation_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "context": enhanced_context
        }
        
        await self.memory_store.store_conversation(conversation_entry)
        self.conversation_history.append(conversation_entry)
        
        return {
            "query": query,
            "context": enhanced_context,
            "suggestions": await self._generate_suggestions(query, enhanced_context),
            "related_files": await self._find_related_files(query, enhanced_context)
        }

    async def _generate_suggestions(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Generate AI suggestions based on query and context"""
        suggestions = []
        
        # Code completion suggestions
        if "completion" in query.lower() or "suggest" in query.lower():
            if context.get("symbols"):
                suggestions.extend([
                    f"Consider using existing symbol: {s['name']}"
                    for s in context["symbols"][:3]
                ])
                
        # Error fixing suggestions
        if "error" in query.lower() or "fix" in query.lower():
            suggestions.append("Check for syntax errors in the current file")
            suggestions.append("Verify all imports are available")
            
        # Refactoring suggestions
        if "refactor" in query.lower() or "improve" in query.lower():
            suggestions.append("Consider extracting repeated code into functions")
            suggestions.append("Add type annotations for better code clarity")
            
        return suggestions


    async def _find_related_files(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Find files related to the query"""
        related_files = []
        
        # Based on dependencies
        if context.get("dependencies"):
            related_files.extend([
                f"Check dependency: {dep}"
                for dep in context["dependencies"][:3]
            ])
            
        # Based on similar patterns
        if context.get("similar_patterns"):
            for pattern in context["similar_patterns"][:2]:
                if pattern.get("context", {}).get("file_path"):
                    related_files.append(f"Similar pattern in: {pattern['context']['file_path']}")
                    
        return related_files
        
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
        return detect_project_language(project_root)
        
    def _generate_diff(self, old_content: str, new_content: str) -> str:
        """Generate a simple diff between old and new content"""
        import difflib
        return '\n'.join(difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            lineterm=''
        ))

    async def _generate_embedding(self, content: str) -> List[float]:
        """Generate semantic embedding for content using SentenceTransformer."""
        if not self.embedding_model:
            await self.logger.warning("Embedding model not available, returning zero vector.")
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
            await self.logger.error(f"Error generating embedding: {e}")
            return [0.0] * 384


    async def get_enhanced_context_for_file(self, file_path: str, line: int = None) -> Dict[str, Any]:
        """Get enhanced context for a file excluding LSP outline"""
        # Ensure appropriate language server is running for this file
        from .language_configs import LanguageConfigs
        language = detect_language_by_extension(Path(file_path).suffix)
        if language != "unknown" and not self.lsp_indexer.lsp_client.is_server_running(language):
            config = LanguageConfigs.get_config(language)
            await self.lsp_indexer.lsp_client.start_server(language, config["command"], self.lsp_indexer.project_root)
            await self.lsp_indexer.lsp_client.initialize_connection(language, self.lsp_indexer.project_root)
        
        # # Ensure file is opened with LSP server
        # await self.lsp_indexer.lsp_client.notify_file_opened(file_path, language)
        
        # Get additional LSP information (excluding outline)
        symbols = await self.lsp_indexer.get_symbols(file_path)
        dependencies = await self.lsp_indexer.get_dependencies(file_path)
        
        return {
            "file_path": file_path,
            "language": language,
            "symbols": symbols,
            "dependencies": dependencies,
            "project_root": str(self.lsp_indexer.project_root)
        }

    async def _initialize_embedding_model(self):
        """Initialize the SentenceTransformer model asynchronously."""
        if self.embedding_model:
            return

        try:
            await self.logger.info("Loading SentenceTransformer model...")
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'
            os.environ['OMP_NUM_THREADS'] = '1'
            
            # Try local model first, then fall back to downloading from Hugging Face
            model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'all-MiniLM-L6-v2')
            
            def _load_model():
                if os.path.exists(model_path):
                    return SentenceTransformer(model_path)
                else:
                    # Download from Hugging Face if local model doesn't exist
                    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            
            self.embedding_model = await asyncio.to_thread(_load_model)
            
            self._embedding_lock = threading.Lock()
            if os.path.exists(model_path):
                await self.logger.info("Successfully loaded local SentenceTransformer model")
            else:
                await self.logger.info("Successfully downloaded SentenceTransformer model from Hugging Face")
        except Exception as e:
            await self.logger.error(f"Error loading SentenceTransformer model: {e}")
            self.embedding_model = None
            self._embedding_lock = None


# Global context manager instance
_context_manager = None


async def get_context_manager(logger: Logger = None) -> AgenticContextManager:
    """Get or create the global context manager instance"""
    global _context_manager
    if _context_manager is None:
        _context_manager = AgenticContextManager(logger)
    return _context_manager