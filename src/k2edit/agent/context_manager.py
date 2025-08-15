"""Agentic Context Manager for K2Edit
Handles AI agent interactions, context management, and orchestration
"""

# Configure multiprocessing FIRST to avoid fork issues on macOS
import os
import multiprocessing
import json
import difflib
import threading
import time
import asyncio
import aiofiles
from aiologger import Logger
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from sentence_transformers import SentenceTransformer

if os.name == 'posix':
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # Already set

# Import performance utilities
from ..utils.async_performance_utils import (
    cpu_bound_task,
    io_bound_task,
    get_performance_monitor,
    ConnectionPool
)

from .memory_config import create_memory_store
from .lsp_indexer import LSPIndexer
from .language_configs import LanguageConfigs
from ..utils.language_utils import detect_language_from_filename, detect_project_language, detect_language_by_extension


@dataclass
class AgentContext:
    """Represents the current context for AI agent operations"""
    file_path: Optional[str] = None
    selected_code: Optional[str] = None
    cursor_position: Optional[Dict[str, int]] = None
    project_root: Optional[str] = None
    language: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    symbols: List[Dict[str, Any]] = field(default_factory=list)
    recent_changes: List[Dict[str, Any]] = field(default_factory=list)


class AgenticContextManager:
    """Manages AI agent context, memory, and LSP integration"""
    
    def __init__(self, logger: Logger, lsp_client=None):
        self.logger = logger
        self.memory_store = create_memory_store(self, self.logger)
        self.lsp_indexer = LSPIndexer(lsp_client=lsp_client, logger=self.logger, memory_store=self.memory_store)
        self.current_context: Optional[AgentContext] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.embedding_model = None
        self._embedding_lock = None
        
        # Performance monitoring
        self.performance_monitor = get_performance_monitor(logger)
        
        # Connection pool for embedding model (singleton pattern)
        self._embedding_pool = None
        
    async def initialize(self, project_root: str, progress_callback=None):
        """Initialize the context manager with project root and progress updates"""
        
        if progress_callback:
            await progress_callback("Initializing memory store...")
        
        # Initialize memory store
        await self.memory_store.initialize(project_root)
        
        # Start embedding model loading in background (non-blocking)
        asyncio.create_task(self._initialize_embedding_model_background(progress_callback))
        
        if progress_callback:
            await progress_callback("Starting symbol indexing...")
        
        # Initialize LSP indexer in background (non-blocking)
        async def _initialize_lsp_background():
            try:
                await self.lsp_indexer.initialize(project_root, progress_callback)
            except (ConnectionError, TimeoutError) as e:
                await self._handle_lsp_error("LSP connection failed", e, progress_callback)
            except (FileNotFoundError, PermissionError) as e:
                await self._handle_lsp_error("LSP file access error", e, progress_callback)
            except Exception as e:
                await self._handle_lsp_error("Failed to initialize LSP indexer", e, progress_callback)
        
        # Start LSP initialization in background
        asyncio.create_task(_initialize_lsp_background())
        
        if progress_callback:
            await progress_callback("LSP indexing started in background...")
        
        # Set initial context
        self.current_context = AgentContext(
            project_root=project_root,
            language=detect_project_language(project_root)
        )
        
        if progress_callback:
            await progress_callback("Agentic system ready")
    
    @property
    def project_root(self):
        """Get the project root from current context"""
        return Path(self.current_context.project_root) if self.current_context else None
        
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
            file_content = await self._read_file_safely(file_path)
            if file_content is None:
                return False
        
        # Store the file as additional context
        context_entry = {
            "type": "additional_file",
            "file_path": file_path,
            "content": file_content,
            "language": detect_language_from_filename(file_path),
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
    
    async def _handle_lsp_error(self, message: str, error: Exception, progress_callback=None):
        """Handle LSP errors with consistent logging and progress updates"""
        await self.logger.error(f"{message}: {error}", exc_info=True)
        if progress_callback:
            await progress_callback(f"Error: {message}: {error}")
    
    async def _read_file_safely(self, file_path: str) -> Optional[str]:
        """Safely read a file with comprehensive error handling"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
        except (FileNotFoundError, PermissionError, UnicodeDecodeError, Exception) as e:
            if isinstance(e, FileNotFoundError):
                await self.logger.error(f"File not found {file_path}: {e}")
            elif isinstance(e, PermissionError):
                await self.logger.error(f"Permission denied reading {file_path}: {e}")
            elif isinstance(e, UnicodeDecodeError):
                await self.logger.error(f"Encoding error reading {file_path}: {e}")
            else:
                await self.logger.error(f"Error reading file {file_path}: {e}")
        return None
        
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

    async def _get_project_overview(self, max_files: int = 30) -> Dict[str, Any]:
        """Get a high-level overview of the project with token limits."""
        if not self.current_context or not self.current_context.project_root:
            return {}

        project_root = Path(self.current_context.project_root)
        overview = {
            "file_structure": await self._analyze_file_structure(self.current_context.project_root, max_files),
            "readme_summary": None
        }

        # Find and summarize README (with character limits)
        readme_files = [p for p in project_root.glob('README*') if p.is_file()]
        if readme_files:
            readme_path = readme_files[0]
            readme_content = await self._read_file_safely(str(readme_path))
            if readme_content:
                # Simple summary: first 10 lines or 500 characters, whichever is smaller
                lines = readme_content.splitlines()[:10]
                summary = "\n".join(lines)
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                overview["readme_summary"] = summary
        
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
                    
            except (ConnectionError, AttributeError, Exception) as e:
                if isinstance(e, (ConnectionError, AttributeError)):
                    await self.logger.error(f"LSP error for file {self.current_context.file_path}: {e}")
                else:
                    await self.logger.error(f"Failed to get LSP context for file: {e}")

        # Determine if this is a general query (affects what context to include)
        is_general_query = not self.current_context.file_path
        
        # Only include project overview for general queries to reduce token usage
        if is_general_query or "project" in query.lower() or "overview" in query.lower():
            context["project_overview"] = await self._get_project_overview()
        else:
            # For specific file queries, only include minimal project info
            context["project_overview"] = {
                "project_root": str(self.lsp_indexer.project_root) if self.lsp_indexer.project_root else None,
                "readme_summary": None  # Skip README for specific queries
            }

        # Only include project-wide symbols when there's no specific file context
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
        # Drastically reduced limits to prevent token explosion
        semantic_results = await self.memory_store.semantic_search(query, limit=2, max_distance=min(0.7, max_semantic_distance))
        
        # Only add semantic context if we have high-quality, relevant results
        # Filter out results that are too short or likely irrelevant
        filtered_semantic = []
        for result in semantic_results or []:
            content = str(result.get('content', ''))
            if len(content) > 20 and len(content) < 1000:  # Reasonable content length
                filtered_semantic.append(result)
        
        context["semantic_context"] = filtered_semantic[:2]  # Maximum 2 results
        
        # Get relevant historical context from memory with very strict filtering
        # Further reduced limit and stricter distance filtering
        relevant_history = await self.memory_store.search_relevant_context(
            query, 
            limit=2,  # Reduced from 3 to 2
            max_distance=min(0.6, max_semantic_distance)  # Even stricter distance filtering
        )
        
        # Filter historical context for quality and size
        filtered_history = []
        for item in relevant_history or []:
            content = str(item.get('content', ''))
            if len(content) > 20 and len(content) < 800:  # Smaller max size for history
                filtered_history.append(item)
        
        context["relevant_history"] = filtered_history[:2]  # Maximum 2 results
        
        # Find similar code patterns if there is a selection (with limits)
        if self.current_context.selected_code:
            similar_patterns = await self.memory_store.find_similar_code(
                self.current_context.selected_code
            )
            # Limit similar patterns to prevent token explosion
            filtered_patterns = []
            for pattern in similar_patterns or []:
                content = str(pattern.get('content', ''))
                if len(content) > 10 and len(content) < 500:  # Small code snippets only
                    filtered_patterns.append(pattern)
            
            context["similar_patterns"] = filtered_patterns[:3]  # Maximum 3 patterns
        else:
            context["similar_patterns"] = []
        
        # Add file_context and project_context for test compatibility
        context["file_context"] = {
            "file_path": context.get("current_file"),
            "language": context.get("language"),
            "symbols": context.get("symbols", []),
            "dependencies": context.get("dependencies", [])
        }
        
        context["project_context"] = {
            "project_root": str(self.lsp_indexer.project_root) if self.lsp_indexer.project_root else None,
            "project_overview": context.get("project_overview", {}),
            "project_symbols": context.get("project_symbols", [])
        }
            
        # Log context size for monitoring
        await self._log_context_size(context)
        
        return context
    
    async def _log_context_size(self, context: Dict[str, Any]) -> None:
        """Log the estimated size of context to monitor token usage"""
        try:
            context_json = json.dumps(context, default=str)
            estimated_tokens = len(context_json) // 4  # Rough estimate: 1 token ≈ 4 characters
            
            await self.logger.info(f"Context size estimate: {len(context_json)} chars, ~{estimated_tokens} tokens")
            
            # Log breakdown of major components
            components = {
                "project_overview": context.get("project_overview", {}),
                "semantic_context": context.get("semantic_context", []),
                "relevant_history": context.get("relevant_history", []),
                "similar_patterns": context.get("similar_patterns", []),
                "project_symbols": context.get("project_symbols", [])
            }
            
            for name, component in components.items():
                if component:
                    component_json = json.dumps(component, default=str)
                    component_tokens = len(component_json) // 4
                    await self.logger.info(f"  {name}: {len(component_json)} chars, ~{component_tokens} tokens")
                    
        except Exception as e:
            await self.logger.warning(f"Failed to log context size: {e}")
        
    async def _analyze_file_structure(self, project_root: str, max_files: int = 50) -> Dict[str, Any]:
        """Analyze project file structure with limits to prevent token explosion"""
        import os
        structure = {
            "root": project_root,
            "files": [],
            "directories": [],
            "language_stats": {},
            "total_files": 0,
            "truncated": False
        }
        
        file_count = 0
        for root, dirs, files in os.walk(project_root):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'dist', 'build', '.git']]
            
            for file in files:
                if not file.startswith('.'):
                    structure["total_files"] += 1
                    
                    # Only include first max_files to prevent token explosion
                    if file_count < max_files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, project_root)
                        
                        # Determine language
                        lang = detect_language_from_filename(file)
                        structure["files"].append({
                            "path": rel_path,
                            "language": lang,
                            "size": os.path.getsize(file_path)
                        })
                        file_count += 1
                    
                    # Always count language stats
                    lang = detect_language_from_filename(file)
                    structure["language_stats"][lang] = structure["language_stats"].get(lang, 0) + 1
        
        if structure["total_files"] > max_files:
            structure["truncated"] = True
            await self.logger.info(f"File structure truncated: showing {max_files} of {structure['total_files']} files")
        
        return structure


        
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
        if "refactor" in query.lower() or "improve" in query.lower() or "optimize" in query.lower():
            suggestions.append("Consider extracting repeated code into functions")
            suggestions.append("Add type annotations for better code clarity")
            if "optimize" in query.lower():
                suggestions.append("Look for performance bottlenecks in loops and data structures")
                suggestions.append("Consider caching frequently computed values")
            
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
            

        
    def _generate_diff(self, old_content: str, new_content: str) -> str:
        """Generate a simple diff between old and new content"""
        return '\n'.join(difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            lineterm=''
        ))

    async def _generate_embedding(self, content: str) -> List[float]:
        """Generate semantic embedding for content using optimized SentenceTransformer."""
        if not self.embedding_model:
            await self.logger.warning("Embedding model not available, returning zero vector.")
            return [0.0] * 384  # Dimension of all-MiniLM-L6-v2 is 384

        # Start performance monitoring
        self.performance_monitor.start_timer("embedding_generation")
        
        try:
            # Use CPU-bound task decorator for embedding generation
            @cpu_bound_task
            def _encode_content(model, text):
                """Encode content using the embedding model in CPU thread pool."""
                return model.encode(
                    text,
                    convert_to_tensor=False,
                    show_progress_bar=False,
                    batch_size=1,
                    device='cpu',
                    normalize_embeddings=True,
                    num_workers=0  # Explicitly disable multiprocessing
                )
            
            # Use connection pool if available, otherwise fall back to direct access
            if self._embedding_pool:
                model = await self._embedding_pool.acquire()
                try:
                    embedding = await _encode_content(model, content)
                finally:
                    await self._embedding_pool.release(model)
            else:
                # Fallback to direct model access with lock
                if self._embedding_lock:
                    with self._embedding_lock:
                        embedding = await _encode_content(self.embedding_model, content)
                else:
                    embedding = await _encode_content(self.embedding_model, content)
            
            # Log performance metrics
            embed_time = self.performance_monitor.end_timer("embedding_generation")
            if embed_time > 1.0:  # Log slow embeddings
                await self.logger.debug(f"Slow embedding generation: {embed_time:.2f}s for {len(content)} chars")
            
            return embedding.tolist()
            
        except (AttributeError, ValueError, RuntimeError) as e:
            self.performance_monitor.end_timer("embedding_generation")
            await self.logger.error(f"Embedding generation error: {e}")
            return [0.0] * 384
        except Exception as e:
            self.performance_monitor.end_timer("embedding_generation")
            await self.logger.error(f"Unexpected embedding error: {e}")
            return [0.0] * 384


    async def get_enhanced_context_for_file(self, file_path: str, line: int = None) -> Dict[str, Any]:
        """Get enhanced context for a file excluding LSP outline"""
        # Ensure appropriate language server is running for this file
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

    async def _initialize_embedding_model_background(self, progress_callback=None):
        """Initialize the SentenceTransformer model in background with performance monitoring."""
        if self.embedding_model:
            return

        # Start performance monitoring
        self.performance_monitor.start_timer("embedding_model_init")
        
        try:
            await self.logger.info("Loading SentenceTransformer model in background...")
            if progress_callback:
                await progress_callback("Loading embedding model...")
            
            # Optimize environment for single-threaded operation
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'
            os.environ['OMP_NUM_THREADS'] = '1'
            os.environ['MKL_NUM_THREADS'] = '1'
            os.environ['NUMEXPR_NUM_THREADS'] = '1'
            
            # Try local model first, then fall back to downloading from Hugging Face
            model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'all-MiniLM-L6-v2')
            
            @io_bound_task
            def _load_model():
                """Load model in I/O thread pool to avoid blocking."""
                if os.path.exists(model_path):
                    return SentenceTransformer(
                        model_path,
                        device='cpu',
                        cache_folder=None  # Disable additional caching
                    )
                else:
                    # Download from Hugging Face if local model doesn't exist
                    return SentenceTransformer(
                        'sentence-transformers/all-MiniLM-L6-v2',
                        device='cpu',
                        cache_folder=None
                    )
            
            # Load model using optimized thread pool
            self.embedding_model = await _load_model()
            
            # Initialize thread lock for model access
            self._embedding_lock = threading.Lock()
            
            # Create connection pool for embedding operations
            async def embedding_factory():
                return self.embedding_model
            
            self._embedding_pool = ConnectionPool(
                factory=embedding_factory,
                max_size=1,  # Single model instance
                health_check=lambda model: model is not None
            )
            
            init_time = self.performance_monitor.end_timer("embedding_model_init")
            
            if os.path.exists(model_path):
                await self.logger.info(f"Successfully loaded local SentenceTransformer model in {init_time:.2f}s")
            else:
                await self.logger.info(f"Successfully loaded SentenceTransformer model from HuggingFace in {init_time:.2f}s")
                
            if progress_callback:
                await progress_callback(f"Embedding model loaded ({init_time:.1f}s)")
                
        except (ImportError, OSError, RuntimeError) as e:
            self._cleanup_embedding_model_on_error(f"Model initialization error: {e}")
        except Exception as e:
            self._cleanup_embedding_model_on_error(f"Unexpected error loading SentenceTransformer model: {e}")
    
    def _cleanup_embedding_model_on_error(self, error_message: str):
        """Clean up embedding model resources on initialization error"""
        self.performance_monitor.end_timer("embedding_model_init")
        asyncio.create_task(self.logger.error(error_message))
        self.embedding_model = None
        self._embedding_lock = None
        self._embedding_pool = None
    
    async def _initialize_embedding_model(self):
        """Initialize the SentenceTransformer model asynchronously (legacy method)."""
        await self._initialize_embedding_model_background()


# Global context manager instance
_context_manager = None


def get_context_manager(logger: Logger, lsp_client=None) -> AgenticContextManager:
    """Factory function to create context manager with proper dependencies"""
    return AgenticContextManager(logger=logger, lsp_client=lsp_client)