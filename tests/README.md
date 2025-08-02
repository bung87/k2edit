# K2Edit Agentic System Tests

This directory contains comprehensive tests for the K2Edit agentic system, including unit tests, integration tests, and performance tests.

## Test Structure

- `test_context_manager.py` - Tests for the AgenticContextManager
- `test_memory_store.py` - Tests for the MemoryStore component
- `test_lsp_indexer.py` - Tests for the LSPIndexer component
- `test_integration.py` - End-to-end integration tests
- `conftest.py` - Pytest configuration and fixtures

## Running Tests

### Quick Start
```bash
# Run all tests
python run_tests.py

# Or run directly with pytest
python -m pytest tests/ -v
```

### Individual Test Suites
```bash
# Run unit tests only
python -m pytest tests/ -v -m unit

# Run integration tests only
python -m pytest tests/ -v -m integration

# Run specific test file
python -m pytest tests/test_context_manager.py -v
```

### With Coverage
```bash
# Run with coverage report
python -m pytest tests/ --cov=agent --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Performance Tests
```bash
# Run with performance benchmarking
python -m pytest tests/test_integration.py::TestIntegration::test_performance_integration -v
```

## Prerequisites

Install test dependencies:
```bash
pip install -r tests/requirements.txt
```

Or install all dependencies:
```bash
pip install -r agent/requirements.txt
pip install -r tests/requirements.txt
```

## Test Categories

### Unit Tests
- Fast, isolated tests for individual components
- Test specific functionality without external dependencies
- Run with: `python -m pytest tests/ -m unit`

### Integration Tests
- Test interactions between components
- Verify system-wide functionality
- Test real-world scenarios
- Run with: `python -m pytest tests/ -m integration`

### Performance Tests
- Measure system performance under load
- Test with large codebases
- Validate memory usage and speed

## Fixtures

The `conftest.py` file provides several useful fixtures:

- `temp_project_dir` - Temporary project directory for testing
- `sample_python_file` - Sample Python file with various constructs
- `sample_js_file` - Sample JavaScript file
- `complex_project` - Multi-file project structure
- `logger` - Configured logger for test output

## Writing New Tests

1. Create new test file: `test_new_feature.py`
2. Follow pytest conventions
3. Use provided fixtures for consistency
4. Add appropriate markers: `@pytest.mark.unit` or `@pytest.mark.integration`
5. Include docstrings for test functions

## Debugging Tests

### Verbose Output
```bash
python -m pytest tests/test_context_manager.py -v -s
```

### Specific Test
```bash
python -m pytest tests/test_memory_store.py::TestMemoryStore::test_store_conversation -v
```

### With Logging
```bash
python -m pytest tests/ -v --log-cli-level=DEBUG
```

## Continuous Integration

The test suite is designed to work with CI systems. Key features:

- Fast unit tests for quick feedback
- Comprehensive integration tests for thorough validation
- Performance benchmarks for regression detection
- Coverage reporting for code quality metrics

## Troubleshooting

### Common Issues

1. **Module not found**: Ensure all dependencies are installed
2. **Async tests failing**: Check asyncio configuration
3. **File permission errors**: Run from project root directory
4. **Slow tests**: Use `-m unit` to run only unit tests

### Debug Mode
```bash
# Enable debug logging
export PYTHONPATH=/Users/bung/py_works/k2edit
python -m pytest tests/ -v --log-cli-level=DEBUG
```

## Test Coverage

Current coverage targets:
- Context Manager: 90%+
- Memory Store: 95%+
- LSP Indexer: 85%+
- Integration: 80%+

View detailed coverage reports in `htmlcov/` directory after running with coverage.