# LSP Server Setup Guide

## Issue: python-lsp-server installed but not in PATH

The enhanced LSP integration in `agent/lsp_indexer.py` requires the Python LSP server to be available. Here's how to resolve the PATH issue:

## Solution 1: Install python-lsp-server globally
```bash
# Install with pip (recommended)
pip install python-lsp-server

# Or with pip3
pip3 install python-lsp-server

# Verify installation
pylsp --help
```

## Solution 2: Use full path to pylsp
Find where pylsp is installed:
```bash
# Find pylsp location
which pylsp
# or
find ~/.local -name "pylsp" 2>/dev/null
# or
python3 -c "import sys; print('\n'.join(sys.path))"
```

Then update the LSP configuration in `agent/lsp_indexer.py` to use the full path.

## Solution 3: Install via package manager (macOS)
```bash
# Using Homebrew
brew install python-lsp-server

# Or via conda
conda install -c conda-forge python-lsp-server
```

## Testing the LSP Integration

Once pylsp is available, test the enhanced features:

```bash
# Test LSP integration
python3 test_lsp_integration.py

# Test with fallback parsing
python3 test_lsp_fallback.py
```

## Enhanced Features Available

The improved LSP integration provides:

1. **Document Outline**: Hierarchical structure of classes, functions, and methods
2. **Enhanced Context**: Rich metadata about code structure
3. **Semantic Search**: Better symbol-based searching
4. **Line-specific Context**: Symbols at specific cursor positions
5. **Fallback Support**: Regex-based parsing when LSP is unavailable

## Configuration

The LSP indexer automatically detects the language server based on file extension:
- Python: `pylsp`
- JavaScript/TypeScript: `typescript-language-server`
- Go: `gopls`
- Rust: `rust-analyzer`

If you need to customize the language server commands, you can modify the `_start_language_server` method in `agent/lsp_indexer.py`.