# Context Optimization Design

## Overview

The K2Edit context optimization system is designed to provide AI agents with relevant, comprehensive context while maintaining manageable token usage. The system dramatically reduced context size from ~2.6 million tokens to manageable levels (~2,335 tokens for specific queries, ~42,707 tokens for general queries).

## Architecture

### Core Components

1. **Context Manager** (`src/k2edit/agent/context_manager.py`)
   - Central orchestrator for context collection and optimization
   - Implements `get_enhanced_context()` method that builds comprehensive context dictionaries
   - Manages token limits and applies filtering strategies

2. **LSP Indexer** (`src/k2edit/agent/lsp_indexer.py`)
   - Provides Language Server Protocol integration for symbol information
   - Indexes project symbols with concurrent processing
   - Supplies `lsp_symbols`, `lsp_dependencies`, and `lsp_metadata`

3. **Kimi API Integration** (`src/k2edit/agent/kimi_api.py`)
   - Handles AI API communication with optimized context
   - Implements comprehensive context logging via `_log_context_details()`
   - Manages conversation flow and iterative processing

### Context Components

The system provides multiple context components based on query type:

#### Core Context (Always Present)
- `current_file`: Current file path and content
- `language`: Detected programming language
- `selected_code`: User-selected code snippet
- `cursor_position`: Current cursor location
- `symbols`: File-level symbols
- `dependencies`: File dependencies
- `recent_changes`: Recent edit history

#### Enhanced Context (Conditional)
- `project_overview`: High-level project structure (for general queries)
- `project_symbols`: Project-wide symbol information (for general queries)
- `semantic_context`: Semantically relevant code context
- `relevant_history`: Related conversation history
- `similar_patterns`: Similar code patterns (when code is selected)
- `file_context`: Extended file context information
- `project_context`: Broader project context

#### LSP-Provided Context
- `lsp_symbols`: Language server symbol information
- `lsp_dependencies`: Dependency analysis from LSP
- `lsp_metadata`: Additional LSP metadata

## Optimization Strategies

### 1. Query Type Detection

```python
def _is_general_query(self, query: str, file_path: Optional[str], selected_code: Optional[str]) -> bool:
    """Determine if query requires project-wide context"""
    if file_path or selected_code:
        return False
    
    general_indicators = [
        "project", "overview", "architecture", "structure",
        "all files", "entire", "whole", "summary"
    ]
    return any(indicator in query.lower() for indicator in general_indicators)
```

### 2. Token-Based Filtering

- **Character-to-Token Estimation**: Uses 4:1 ratio for quick estimation
- **Component Prioritization**: Essential components loaded first
- **Truncation Strategies**: Large components truncated when necessary
- **File Structure Limits**: Project structure limited to 30 files for overview

### 3. Concurrent Processing

- **Symbol Indexing**: Uses configurable worker pools (default: 5 workers)
- **Batch Processing**: Processes files in batches to manage memory
- **Async Operations**: Non-blocking operations where possible

### 4. Memory Management

- **Embedding Caching**: Reuses embeddings when available
- **Lazy Loading**: Components loaded only when needed
- **Resource Cleanup**: Proper cleanup of LSP connections and workers

## Context Flow

```
User Query → Context Manager → Enhanced Context Building
     ↓
┌─────────────────────────────────────────────────────┐
│ Context Components Assembly                         │
├─────────────────────────────────────────────────────┤
│ 1. Core Context (file, language, selection)        │
│ 2. LSP Context (symbols, dependencies)             │
│ 3. Semantic Context (embeddings, history)          │
│ 4. Project Context (overview, symbols)             │
└─────────────────────────────────────────────────────┘
     ↓
Token Estimation → Filtering → Kimi API → AI Response
```

## Logging and Monitoring

### Context Size Logging

```python
def _log_context_size(self, context: Dict[str, Any]) -> None:
    """Log detailed context size information"""
    total_chars = sum(len(str(v)) for v in context.values())
    estimated_tokens = total_chars // 4
    
    self.logger.info(f"Context size estimate: {total_chars} chars, ~{estimated_tokens} tokens")
    
    for key, value in context.items():
        if value:
            chars = len(str(value))
            tokens = chars // 4
            self.logger.info(f"  {key}: {chars} chars, ~{tokens} tokens")
```

### Component Tracking

The system logs:
- Individual component sizes and token estimates
- Total context size before and after optimization
- Query type detection results
- Symbol collection statistics
- Performance metrics (indexing time, API response time)

## Performance Characteristics

### Before Optimization
- Context size: ~2.6 million tokens
- Unusable due to API limits
- Poor response quality due to information overload

### After Optimization
- **Specific queries**: ~2,335 tokens (99.9% reduction)
- **General queries**: ~42,707 tokens (98.4% reduction)
- Maintains comprehensive context coverage
- Improved AI response quality and relevance

## Configuration

### Token Limits
```python
MAX_CONTEXT_TOKENS = 100000  # Maximum context size
FILE_STRUCTURE_LIMIT = 30    # Max files in project overview
CONCURRENT_WORKERS = 5       # Symbol indexing workers
```

### Query Classification
- General query indicators: project, overview, architecture, structure
- Specific query indicators: presence of file_path or selected_code

## Error Handling

- **LSP Failures**: Graceful degradation when LSP unavailable
- **Embedding Errors**: Fallback to zero vectors
- **Token Overflow**: Automatic truncation with priority preservation
- **API Rate Limits**: Exponential backoff and retry logic

## Future Enhancements

1. **Adaptive Token Limits**: Dynamic adjustment based on query complexity
2. **Semantic Chunking**: Intelligent code splitting for large files
3. **Context Caching**: Persistent caching of frequently accessed context
4. **Multi-Model Support**: Context optimization for different AI models
5. **Real-time Context Updates**: Live context updates during editing

## Testing

The system includes comprehensive tests covering:
- Context size optimization (`test_context_optimization.py`)
- Component filtering and truncation
- LSP integration and symbol indexing
- Memory usage and performance
- Error handling and edge cases

Run context-related tests with:
```bash
pytest tests/test_context_*.py -v
```