# K2Edit Agentic System

A comprehensive solution for agentic context, memory, and LSP indexing in the K2Edit text editor.

## Overview

The agentic system provides intelligent code assistance through:
- **Agentic Context**: Enhanced context awareness for AI interactions
- **Memory System**: Persistent storage of conversations and code changes
- **LSP Integration**: Real-time code intelligence via Language Server Protocol

## Architecture

```
agent/
├── __init__.py          # Main API and initialization
├── context_manager.py   # Context enhancement and management
├── memory_store.py      # Persistent storage system
├── lsp_indexer.py       # LSP integration and symbol indexing
└── integration.py       # K2Edit integration helpers
```

## Features

### 1. Agentic Context Manager
- **Real-time context building** from current file, cursor position, and selected code
- **Symbol resolution** using LSP integration
- **Dependency tracking** across files and modules
- **Pattern matching** for similar code structures
- **Cross-reference generation** for symbol usage

### 2. Memory Store
- **Conversation history** with full context
- **Code change tracking** with before/after snapshots
- **Pattern learning** from user interactions
- **Searchable memory** across all stored data
- **Automatic cleanup** with configurable retention

### 3. LSP Indexer
- **Multi-language support** (Python, JavaScript, TypeScript, etc.)
- **Symbol indexing** with full metadata
- **Real-time updates** as files change
- **Cross-reference resolution**
- **Dependency analysis**

## Quick Start

### 1. Initialize the System

```python
import asyncio
from agent import initialize_agentic_system

async def setup_agent():
    agent = await initialize_agentic_system("/path/to/project")
    return agent

# Run initialization
agent = asyncio.run(setup_agent())
```

### 2. Process Queries

```python
from agent import process_agent_query

# Process a code completion query
result = await process_agent_query(
    query="suggest improvements for this function",
    file_path="main.py",
    selected_code="def my_function():\n    pass",
    cursor_position={"line": 10, "column": 4}
)

print("Suggestions:", result["suggestions"])
print("Related files:", result["related_files"])
```

### 3. Record Changes

```python
from agent import record_code_change

# Record a code change
await record_code_change(
    file_path="example.py",
    change_type="modify",
    old_content="def old_function():\n    pass",
    new_content="def improved_function():\n    return True"
)
```

### 4. Get Code Intelligence

```python
from agent import get_code_intelligence

# Get comprehensive intelligence for a file
intelligence = await get_code_intelligence("main.py")

print("Symbols:", intelligence["symbols"])
print("Dependencies:", intelligence["dependencies"])
print("Cross-references:", intelligence["cross_references"])
```

## Integration with K2Edit

### Step 1: Import and Initialize

In your K2Edit main application:

```python
from agent import initialize_agentic_system, process_agent_query, record_code_change

class K2EditApp(App):
    async def on_mount(self):
        # Initialize agentic system
        await initialize_agentic_system(str(Path.cwd()))
        
    async def on_code_change(self, file_path, old_content, new_content):
        # Record code changes
        await record_code_change(
            file_path, "modify", old_content, new_content
        )
        
    async def handle_ai_query(self, query):
        # Process AI queries with full context
        result = await process_agent_query(
            query=query,
            file_path=self.current_file,
            selected_code=self.selected_text,
            cursor_position=self.cursor_position
        )
        return result
```

### Step 2: Enhanced AI Panel

Update your AI response panel to use agentic context:

```python
class OutputPanel(Widget):
    async def process_query(self, query: str):
        # Get enhanced context
        result = await process_agent_query(
            query=query,
            file_path=self.app.current_file,
            selected_code=self.app.selected_text,
            cursor_position=self.app.cursor_position
        )
        
        # Display results
        self.display_suggestions(result["suggestions"])
        self.display_related_files(result["related_files"])
        self.display_ai_response(result["context"])
```

## Configuration

The agentic system can be configured via environment variables or configuration files:

```python
# Default configuration
DEFAULT_AGENT_CONFIG = {
    "memory_retention_days": 30,
    "max_conversation_history": 100,
    "enable_lsp_indexing": True,
    "symbol_refresh_interval": 300,  # seconds
    "similarity_threshold": 0.7
}
```

### Environment Variables

```bash
# Memory settings
K2EDIT_MEMORY_RETENTION_DAYS=30
K2EDIT_MAX_CONVERSATIONS=100

# LSP settings
K2EDIT_ENABLE_LSP=true
K2EDIT_LSP_REFRESH_INTERVAL=300

# Advanced settings
K2EDIT_SIMILARITY_THRESHOLD=0.7
```

## Advanced Usage

### Custom Context Enhancement

```python
from agent.context_manager import AgenticContextManager

class CustomContextManager(AgenticContextManager):
    async def enhance_context(self, query, file_path, selected_code, cursor_position):
        # Add custom context enhancement
        base_context = await super().enhance_context(...)
        
        # Add project-specific context
        base_context["project_structure"] = await self.get_project_structure()
        base_context["recent_commits"] = await self.get_git_history()
        
        return base_context
```

### Memory Extensions

```python
from agent.chroma_memory_store import ChromaMemoryStore

class CustomMemoryStore(ChromaMemoryStore):
    async def store_custom_data(self, data_type: str, data: dict):
        # Store custom data types
        await self.store_memory(
            memory_type="custom",
            content={"type": data_type, "data": data},
            context={"source": "custom_extension"}
        )
```

## Troubleshooting

### Common Issues

1. **LSP Server Not Starting**
   - Ensure language servers are installed (e.g., `pylsp` for Python)
   - Check PATH configuration
   - Verify project structure

2. **Memory Database Issues**
   - Check file permissions for `.k2edit/chroma_db/` directory
   - Clear memory with: `rm -rf .k2edit/chroma_db/`

3. **Performance Issues**
   - Reduce symbol refresh interval
   - Limit memory retention period
   - Disable LSP for large projects

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("k2edit.agent")
```

## API Reference

### Core Functions

- `initialize_agentic_system(project_root, logger=None)`
- `process_agent_query(query, file_path=None, selected_code=None, cursor_position=None)`
- `record_code_change(file_path, change_type, old_content, new_content)`
- `get_code_intelligence(file_path)`
- `shutdown_agentic_system()`

### Memory Store Methods

- `store_conversation(query, response, context)`
- `store_context_change(file_path, context_type, content)`
- `store_pattern(pattern, context, metadata)`
- `get_recent_conversations(limit=10)`
- `get_file_context(file_path)`
- `find_similar_patterns(pattern, threshold=0.7)`

### LSP Indexer Methods

- `get_symbols(file_path)`
- `get_dependencies(file_path)`
- `find_symbol_references(symbol_name)`
- `get_file_info(file_path)`
- `refresh_index(file_path=None)`

## Usage

The agentic system is automatically integrated into the K2Edit application. When you run the main application, the agentic features are available through:

- **AI queries**: Use the command bar (`Ctrl+K`) to ask AI questions
- **Context awareness**: Files are automatically added to context when opened
- **Memory tracking**: Code changes are automatically recorded
- **Code intelligence**: Available through the integrated UI

To start the application:

```bash
cd /path/to/k2edit
python main.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.