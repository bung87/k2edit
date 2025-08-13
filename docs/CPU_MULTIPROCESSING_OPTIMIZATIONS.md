# CPU and Multiprocessing Optimizations

## Overview

This document outlines the comprehensive CPU and multiprocessing optimizations implemented across the k2edit codebase to improve performance for computationally intensive operations.

## Optimization Strategy

The optimization approach follows a hybrid strategy:

1. **Async I/O for I/O-bound operations** (previously implemented)
2. **Multiprocessing for CPU-bound operations** (new implementation)
3. **Intelligent threshold-based switching** between sequential and parallel processing
4. **Performance monitoring and metrics collection**

## Key Optimizations Implemented

### 1. Search Manager Optimizations (`src/k2edit/utils/search_manager.py`)

**Problem**: Large-scale file searching was CPU-intensive, especially with regex patterns and multiple file types.

**Solution**:
- Added multiprocessing support for file sets larger than 50 files
- Implemented `_search_files_multiprocess()` method with optimal process count calculation
- Created worker function `_search_file_chunk()` for parallel file processing
- Maintained async I/O for smaller file sets to avoid multiprocessing overhead

**Performance Impact**:
- **50+ files**: Uses multiprocessing with up to `min(cpu_count, files//20)` processes
- **<50 files**: Uses async I/O for optimal performance
- Automatic load balancing based on file count

```python
# Automatic optimization based on file count
if len(files_list) > 50:
    results = await self._search_files_multiprocess(files_list, pattern, case_sensitive, regex)
else:
    results = await self._search_files_async(files_list, pattern, case_sensitive, regex)
```

### 2. ChromaDB Memory Store Optimizations (`src/k2edit/agent/chroma_memory_store.py`)

**Problem**: Large result sets from semantic search required CPU-intensive processing for distance calculations, JSON parsing, and quality filtering.

**Solution**:
- Added multiprocessing support for result sets larger than 30 items
- Implemented `_process_search_results_multiprocess()` for parallel result processing
- Created worker functions for distance filtering and quality checks
- Maintained sequential processing for smaller result sets

**Performance Impact**:
- **30+ results**: Uses multiprocessing with up to `min(cpu_count, results//15)` processes
- **<30 results**: Uses sequential processing to avoid overhead
- Optimized distance calculations and content parsing

```python
# Intelligent processing strategy
if len(doc_ids) > 30:
    search_results = await self._process_search_results_multiprocess(
        doc_ids, documents, metadatas, distances, max_distance
    )
else:
    search_results = await self._process_search_results_sequential(
        doc_ids, documents, metadatas, distances, max_distance
    )
```

### 3. CPU Optimization Framework (`src/k2edit/utils/cpu_optimization.py`)

**Problem**: Need for a unified approach to CPU optimization across the codebase.

**Solution**:
- Created comprehensive `CPUOptimizer` class with performance monitoring
- Implemented automatic threshold-based optimization
- Added performance metrics collection and analysis
- Created `@cpu_optimized` decorator for easy integration

**Key Features**:
- **Automatic Strategy Selection**: Chooses between sequential and multiprocessing based on data size
- **Performance Monitoring**: Tracks CPU usage, memory usage, execution time, and throughput
- **Resource Management**: Proper cleanup of process pools and thread pools
- **Error Handling**: Graceful fallback to sequential processing on multiprocessing failures

## Performance Thresholds

| Operation Type | Sequential Threshold | Multiprocessing Threshold | Optimal Process Count |
|----------------|---------------------|---------------------------|----------------------|
| File Search | < 50 files | ≥ 50 files | `min(cpu_count, files//20)` |
| Search Results | < 30 results | ≥ 30 results | `min(cpu_count, results//15)` |
| Batch Operations | < 50 items | ≥ 50 items | `min(cpu_count, items//20)` |

## Implementation Details

### Multiprocessing Worker Functions

```python
def _search_file_chunk(file_chunk: List[Path], pattern: str, 
                      case_sensitive: bool, regex: bool) -> List[FileSearchResult]:
    """Worker function for multiprocessing file search."""
    results = []
    for file_path in file_chunk:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            temp_manager = SearchManager()
            matches = temp_manager.search_in_text(content, pattern, case_sensitive, regex)
            
            if matches:
                file_matches = [(match.start_line + 1, match.start_col, match.text) 
                              for match in matches]
                results.append(FileSearchResult(str(file_path), file_matches))
        except (UnicodeDecodeError, PermissionError, OSError):
            continue
    return results
```

### Performance Metrics Collection

```python
@dataclass
class PerformanceMetrics:
    operation_name: str
    execution_time: float
    cpu_usage_before: float
    cpu_usage_after: float
    memory_usage_before: float
    memory_usage_after: float
    process_count: int
    input_size: int
    throughput: float  # items per second
```

## Usage Examples

### Using the CPU Optimizer

```python
from src.k2edit.utils.cpu_optimization import CPUOptimizer

optimizer = CPUOptimizer(logger=your_logger)

# Optimize batch operation
results = await optimizer.optimize_batch_operation(
    operation_func=process_item,
    data_items=large_dataset,
    operation_name="data_processing"
)

# Get performance summary
summary = optimizer.get_performance_summary()
print(f"Average throughput: {summary['average_throughput']} items/s")
```

### Using the Decorator

```python
from src.k2edit.utils.cpu_optimization import cpu_optimized

@cpu_optimized(operation_name="text_analysis", threshold=100)
async def analyze_texts(texts: List[str]) -> List[Dict]:
    # Function automatically uses multiprocessing for >100 texts
    return [analyze_single_text(text) for text in texts]
```

## Performance Benefits

### Expected Improvements

1. **File Search Operations**:
   - 2-4x speedup for large file sets (>100 files)
   - Maintained efficiency for small file sets
   - Better CPU utilization across multiple cores

2. **Semantic Search Results**:
   - 1.5-3x speedup for large result sets (>50 results)
   - Reduced memory pressure through chunked processing
   - Improved response times for complex queries

3. **Batch Operations**:
   - Scalable performance based on available CPU cores
   - Automatic optimization without code changes
   - Comprehensive performance monitoring

### Resource Utilization

- **CPU Usage**: Better distribution across available cores
- **Memory Usage**: Controlled through chunked processing
- **I/O Efficiency**: Maintained async I/O for file operations
- **Process Management**: Automatic cleanup and resource management

## Error Handling and Fallbacks

### Graceful Degradation

1. **Multiprocessing Failures**: Automatic fallback to sequential processing
2. **Resource Constraints**: Dynamic process count adjustment
3. **Memory Pressure**: Chunked processing to prevent memory exhaustion
4. **File Access Errors**: Individual file error handling without stopping batch operations

### Logging and Monitoring

```python
# Performance logging
if self.logger:
    await self.logger.info(
        f"CPU optimization - {operation_name}: {input_size} items, "
        f"{execution_time:.3f}s, {throughput:.1f} items/s, "
        f"{process_count} processes"
    )
```

## Integration with Existing Systems

### Compatibility

- **Async/Await**: Full compatibility with existing async codebase
- **Error Handling**: Maintains existing error handling patterns
- **Logging**: Integrates with existing aiologger infrastructure
- **Configuration**: Respects existing performance settings

### Migration Path

1. **Phase 1**: Core optimizations in search and memory systems (✅ Complete)
2. **Phase 2**: Integration with LSP indexing and symbol processing
3. **Phase 3**: UI rendering optimizations for large datasets
4. **Phase 4**: Comprehensive performance monitoring dashboard

## Monitoring and Maintenance

### Performance Metrics

- **Execution Time**: Track operation duration
- **Throughput**: Items processed per second
- **CPU Impact**: Before/after CPU usage
- **Memory Impact**: Memory usage changes
- **Process Efficiency**: Optimal process count usage

### Maintenance Tasks

1. **Regular Performance Reviews**: Monthly analysis of metrics
2. **Threshold Tuning**: Adjust based on real-world usage patterns
3. **Resource Monitoring**: Track system resource utilization
4. **Error Analysis**: Review multiprocessing failures and optimize

## Future Enhancements

### Planned Improvements

1. **GPU Acceleration**: For suitable operations (embeddings, large-scale text processing)
2. **Distributed Processing**: Multi-machine processing for very large datasets
3. **Adaptive Thresholds**: Machine learning-based threshold optimization
4. **Real-time Monitoring**: Live performance dashboard
5. **Memory-mapped Files**: For very large file processing

### Research Areas

1. **Hybrid Processing**: Combining multiprocessing with async I/O more efficiently
2. **Cache Optimization**: Intelligent caching for repeated operations
3. **Load Balancing**: Dynamic work distribution based on system load
4. **Resource Prediction**: Predicting optimal resource allocation

## Conclusion

The implemented CPU and multiprocessing optimizations provide:

- **Significant performance improvements** for large-scale operations
- **Intelligent resource utilization** based on workload characteristics
- **Comprehensive monitoring** for continuous optimization
- **Graceful error handling** with automatic fallbacks
- **Easy integration** with existing codebase patterns

These optimizations complement the existing async I/O improvements to create a comprehensive performance optimization framework that scales efficiently with workload size and system resources.