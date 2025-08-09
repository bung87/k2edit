# ChromaDB Integration for K2Edit

This document explains how to use ChromaDB as an alternative to SQLite for memory storage in K2Edit, which provides native vector embedding support and can resolve the "fds_to_keep" multiprocessing error on macOS.

## Overview

K2Edit now supports two memory storage backends:

1. **SQLite** (default) - Traditional relational database with manual embedding storage
2. **ChromaDB** (alternative) - Vector database with native embedding support

## Why Use ChromaDB?

### Benefits

- **Native Vector Support**: ChromaDB is designed specifically for vector embeddings
- **Resolves macOS Issues**: Eliminates the "bad value(s) in fds_to_keep" multiprocessing error
- **Better Performance**: Optimized for semantic search and similarity queries
- **Scalability**: Handles large codebases more efficiently
- **Simplified Architecture**: No manual embedding serialization/deserialization

### When to Use ChromaDB

- You're experiencing multiprocessing errors on macOS
- Your project has a large codebase with many files
- You need high-performance semantic search
- You want to leverage advanced vector database features

## Installation

### 1. Install ChromaDB

ChromaDB is already included in the requirements.txt file:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install chromadb>=0.4.0
```

### 2. Configure K2Edit

ChromaDB is now the default and only memory store for K2Edit. No configuration is needed.

## Usage

ChromaDB works transparently with K2Edit as the default memory store:

```bash
# Start K2Edit (ChromaDB is the default)
python main.py
```

#### Programmatic Usage

```python
from agent.memory_config import create_memory_store

# Create ChromaDB memory store (default)
memory_store = create_memory_store(context_manager)
```

## Storage Structure

### File Locations

- **SQLite**: `.k2edit/memory.db`
- **ChromaDB**: `.k2edit/chroma_db/`

### ChromaDB Collections

ChromaDB organizes data into collections:

1. **memories** - General memory storage (conversations, context, patterns)
2. **code_patterns** - Reusable code snippets and patterns
3. **relationships** - Context relationships between memory items

## Usage Examples

### Basic Usage

```python
import os
os.environ["K2EDIT_MEMORY_STORE"] = "chromadb"

from agent.context_manager import AgenticContextManager
from aiologger import Logger

# Initialize context manager with required logger
logger = Logger.with_default_handlers(name="k2edit")
context_manager = AgenticContextManager(logger=logger)
await context_manager.initialize("/path/to/project")

# The memory store will automatically be ChromaDB
memory_store = context_manager.memory_store
print(type(memory_store).__name__)  # ChromaMemoryStore
```

### Storing Data

```python
# Store conversation
await memory_store.store_conversation({
    "query": "How do I implement async functions?",
    "response": "Use async def and await keywords...",
    "context": {"file_path": "main.py"}
})

# Store code context
await memory_store.store_context("utils.py", {
    "language": "python",
    "symbols": ["helper_function", "UtilityClass"],
    "dependencies": ["requests", "json"]
})

# Store code pattern
await memory_store.store_pattern(
    "error_handling",
    "try:\n    # code\nexcept Exception as e:\n    logger.error(e)",
    {"language": "python", "category": "error_handling"}
)
```

### Searching Data

```python
# Semantic search
results = await memory_store.semantic_search("async programming", limit=5)
for result in results:
    print(f"Similarity: {result['similarity']:.3f}")
    print(f"Content: {result['content']}")

# Find similar code
similar = await memory_store.find_similar_code("async def main():", limit=3)
for code in similar:
    print(f"Usage count: {code['usage_count']}")
    print(f"Pattern: {code['content']}")

# Get recent conversations
recent = await memory_store.get_recent_conversations(limit=10)
for conv in recent:
    print(f"Query: {conv['content']['query']}")
```



## Performance Considerations

### ChromaDB Advantages

- **Faster Semantic Search**: Native vector operations
- **Better Scaling**: Optimized for large datasets
- **Memory Efficiency**: Efficient vector storage
- **Concurrent Access**: Better handling of concurrent operations

### SQLite Advantages

- **Smaller Footprint**: Single file storage
- **Simpler Deployment**: No additional dependencies
- **Familiar**: Standard SQL operations

## Troubleshooting

### Common Issues

#### ChromaDB Installation Issues

```bash
# If you encounter installation issues
pip install --upgrade chromadb

# For Apple Silicon Macs
pip install chromadb --no-binary=chromadb
```

#### Permission Issues

```bash
# Ensure write permissions to project directory
chmod -R 755 .k2edit/
```

#### Memory Issues

```python
# Reduce batch size for large datasets
config = MemoryStoreConfig(
    store_type="chromadb",
    chroma_settings={
        "max_batch_size": 100  # Reduce if memory issues
    }
)
```

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Check which memory store is being used
logger.info(f"Using memory store: {type(memory_store).__name__}")
```

## API Compatibility

The ChromaDB memory store implements the same interface as the SQLite memory store, ensuring compatibility:

- `store_conversation()`
- `store_context()`
- `store_change()`
- `store_pattern()`
- `semantic_search()`
- `find_similar_code()`
- `get_recent_conversations()`
- `get_file_context()`

## Advanced Configuration

### Custom ChromaDB Settings

```python
config = MemoryStoreConfig(
    store_type="chromadb",
    chroma_settings={
        "anonymized_telemetry": False,
        "allow_reset": True,
        "max_batch_size": 1000,
        "persist_directory": "/custom/path/chroma_db"
    }
)
```

### Remote ChromaDB Server

```python
config = MemoryStoreConfig(
    store_type="chromadb",
    chroma_host="localhost",
    chroma_port=8000
)
```

## Best Practices

1. **Use Environment Variables**: Set `K2EDIT_MEMORY_STORE=chromadb` for consistent configuration
2. **Monitor Storage**: ChromaDB creates multiple files; monitor disk usage
3. **Backup Data**: Regularly export important memories
4. **Performance Tuning**: Adjust batch sizes based on your system
5. **Version Control**: Add `.k2edit/chroma_db/` to `.gitignore`

## Future Enhancements

- Automatic migration tool from SQLite to ChromaDB
- Remote ChromaDB server support
- Advanced vector search configurations
- Memory store analytics and insights
- Hybrid storage (SQLite + ChromaDB)

## Support

For issues related to ChromaDB integration:

1. Check the troubleshooting section above
2. Enable debug logging to identify the issue
3. Verify ChromaDB installation: `python -c "import chromadb; print('OK')"`
4. Check file permissions in the `.k2edit/` directory

For ChromaDB-specific issues, refer to the [ChromaDB documentation](https://docs.trychroma.com/).