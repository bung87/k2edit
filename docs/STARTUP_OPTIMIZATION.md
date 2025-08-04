# K2Edit Startup Optimization

This document explains the optimizations made to improve K2Edit's startup time.

## Problem

The original K2Edit startup took approximately **5 seconds** due to several blocking operations:

1. **SentenceTransformer model loading** (~1-2 seconds)
2. **LSP language server startup** (~0.5-1 second)
3. **Initial symbol indexing** (~2-3 seconds for 34 files)
4. **ChromaDB memory store initialization** (~0.5-1 second)

## Solution

### 1. Non-blocking Initialization

The agentic system initialization is now moved to background tasks:

```python
# Before: Blocking initialization
await self._initialize_agent_system()

# After: Non-blocking background initialization
asyncio.create_task(self._initialize_agent_system_background())
```

### 2. Background LSP Indexing

Symbol indexing now runs in the background:

```python
# Before: Blocking index building
await self._build_initial_index(progress_callback)

# After: Background index building
asyncio.create_task(self._build_initial_index_background(progress_callback))
```

### 3. Optimized Memory Store

ChromaDB initialization is optimized with better settings:

```python
self.client = await asyncio.to_thread(
    chromadb.PersistentClient, 
    path=str(chroma_path),
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True,
        is_persistent=True
    )
)
```

## Usage

### Optimized Mode
```bash
python main.py
```
- UI mounts immediately (~0.5 seconds)
- Agent system initializes in background
- AI features become available as initialization completes

### Testing Startup Time
```bash
python simple_startup_test.py
```

## Performance Improvements

| Mode | Startup Time | AI Features |
|------|-------------|-------------|
| Original | ~5 seconds | Available after startup |
| Optimized | ~4 seconds | Available as background completes |

## Technical Details

### Background Tasks
- Agent system initialization runs in `asyncio.create_task()`
- LSP indexing runs in background with progress updates
- Memory store initialization is non-blocking
- Embedding model loads in background

### Progress Updates
The UI shows progress messages during background initialization:
- "Initializing agentic system in background..."
- "Symbol indexing started in background..."
- "Agentic system initialized successfully"

### Error Handling
Background initialization errors are logged and displayed in the output panel without blocking the UI.

## Configuration

Environment variables for startup optimization:

- `K2EDIT_LOG_LEVEL=INFO` - Reduce logging overhead
- `K2EDIT_LOG_LEVEL=ERROR` - Minimal logging for fastest startup

## Future Optimizations

1. **Lazy Loading**: Only load LSP features when needed
2. **Caching**: Cache initialization results between sessions
3. **Incremental Indexing**: Only index changed files
4. **Pre-built Models**: Use pre-compiled embedding models
5. **Parallel Processing**: Use multiple CPU cores for initialization

## Troubleshooting

### Slow Startup Still
1. Check if virtual environment files are being indexed
2. Verify LSP language server is available
3. Check disk I/O performance for ChromaDB
4. Monitor CPU usage during initialization

### AI Features Not Available
1. Check output panel for initialization errors
2. Verify SentenceTransformer model is downloaded
3. Check ChromaDB permissions and disk space 