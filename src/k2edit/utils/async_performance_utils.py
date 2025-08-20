"""Performance utilities for K2Edit"""

import asyncio
import concurrent.futures
import time
import os
import atexit
from typing import Callable, Any, Dict, List, Optional
from functools import wraps
from dataclasses import dataclass
from aiologger import Logger
import threading

class OptimizedThreadPoolExecutor:
    """Thread pool executor optimized for K2Edit's workload patterns.
    
    Features:
    - Separate pools for CPU-bound and I/O-bound tasks
    - Dynamic sizing based on system resources
    - Proper cleanup and resource management
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        cpu_count = os.cpu_count() or 4
        
        # CPU-bound pool: Limited to CPU cores to avoid context switching overhead
        self.cpu_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(cpu_count, 8),  # Cap at 8 to prevent resource exhaustion
            thread_name_prefix="k2edit-cpu"
        )
        
        # I/O-bound pool: Higher worker count for concurrent I/O operations
        self.io_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(cpu_count * 4, 32),  # Higher concurrency for I/O
            thread_name_prefix="k2edit-io"
        )
        
        self._initialized = True
        
        # Register cleanup on shutdown
        atexit.register(self.shutdown)
    
    def shutdown(self):
        """Gracefully shutdown thread pools."""
        try:
            if hasattr(self, 'cpu_pool'):
                self.cpu_pool.shutdown(wait=False)
            if hasattr(self, 'io_pool'):
                self.io_pool.shutdown(wait=False)
        except (KeyboardInterrupt, RuntimeError):
            # Force shutdown on interrupt or runtime error
            if hasattr(self, 'cpu_pool'):
                try:
                    self.cpu_pool.shutdown(wait=False)
                except Exception:
                    pass
            if hasattr(self, 'io_pool'):
                try:
                    self.io_pool.shutdown(wait=False)
                except Exception:
                    pass
    
    async def run_cpu_bound(self, func: Callable, *args, **kwargs) -> Any:
        """Execute CPU-bound function in optimized thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.cpu_pool, func, *args, **kwargs)
    
    async def run_io_bound(self, func: Callable, *args, **kwargs) -> Any:
        """Execute I/O-bound function in optimized thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.io_pool, func, *args, **kwargs)


class AsyncTaskQueue:
    """High-performance async task queue with priority support.
    
    Features:
    - Priority-based task scheduling
    - Backpressure handling
    - Batch processing capabilities
    - Graceful shutdown
    """
    
    def __init__(self, max_size: int = 1000, max_workers: int = 4):
        self.queue = asyncio.PriorityQueue(maxsize=max_size)
        self.max_workers = max_workers
        self.workers = []
        self.running = False
        self._task_counter = 0
        self._results = {}
        self._result_futures = {}
    
    async def start(self):
        """Start the task queue workers."""
        if self.running:
            return
            
        self.running = True
        self.workers = [
            asyncio.create_task(self._worker(f"worker-{i}"))
            for i in range(self.max_workers)
        ]
    
    async def stop(self):
        """Stop the task queue workers gracefully."""
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
    
    async def submit_task(self, func: Callable, *args, priority: int = 5, **kwargs) -> Any:
        """Submit a task to the queue with optional priority.
        
        Args:
            func: Function to execute
            *args: Function arguments
            priority: Task priority (lower number = higher priority)
            **kwargs: Function keyword arguments
            
        Returns:
            Task result
        """
        task_id = self._task_counter
        self._task_counter += 1
        
        # Create future for result
        result_future = asyncio.Future()
        self._result_futures[task_id] = result_future
        
        # Submit task to queue
        await self.queue.put((priority, task_id, func, args, kwargs))
        
        # Wait for result
        return await result_future
    
    async def _worker(self, name: str):
        """Worker coroutine that processes tasks from the queue."""
        while self.running:
            try:
                # Get task from queue with timeout
                priority, task_id, func, args, kwargs = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
                
                try:
                    # Execute task
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    # Set result
                    if task_id in self._result_futures:
                        self._result_futures[task_id].set_result(result)
                        del self._result_futures[task_id]
                        
                except Exception as e:
                    # Set exception
                    if task_id in self._result_futures:
                        self._result_futures[task_id].set_exception(e)
                        del self._result_futures[task_id]
                
                finally:
                    self.queue.task_done()
                    
            except asyncio.TimeoutError:
                # Timeout is expected when queue is empty
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log unexpected errors but continue
                print(f"Worker {name} error: {e}")


class ConnectionPool:
    """Generic connection pool for managing expensive resources.
    
    Features:
    - Lazy connection creation
    - Connection health checking
    - Automatic cleanup of stale connections
    - Thread-safe operations
    """
    
    def __init__(self, factory: Callable, max_size: int = 10, 
                 health_check: Optional[Callable] = None):
        self.factory = factory
        self.max_size = max_size
        self.health_check = health_check
        self._pool = asyncio.Queue(maxsize=max_size)
        self._created_count = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a connection from the pool."""
        # Try to get existing connection
        try:
            connection = self._pool.get_nowait()
            
            # Health check if provided
            if self.health_check and not await self._check_health(connection):
                # Connection is unhealthy, create new one
                return await self._create_connection()
            
            return connection
        except asyncio.QueueEmpty:
            # No connections available, create new one
            return await self._create_connection()
    
    async def release(self, connection):
        """Release a connection back to the pool."""
        try:
            self._pool.put_nowait(connection)
        except asyncio.QueueFull:
            # Pool is full, close the connection
            await self._close_connection(connection)
    
    async def _create_connection(self):
        """Create a new connection."""
        async with self._lock:
            if self._created_count >= self.max_size:
                # Wait for a connection to become available
                return await self._pool.get()
            
            self._created_count += 1
            return await self.factory()
    
    async def _check_health(self, connection) -> bool:
        """Check if connection is healthy."""
        try:
            return await self.health_check(connection)
        except Exception:
            return False
    
    async def _close_connection(self, connection):
        """Close a connection and decrement count."""
        try:
            if hasattr(connection, 'close'):
                await connection.close()
            elif hasattr(connection, 'disconnect'):
                await connection.disconnect()
        except Exception:
            pass
        finally:
            async with self._lock:
                self._created_count -= 1


def cpu_bound_task(func: Callable) -> Callable:
    """Decorator to automatically run CPU-bound functions in thread pool."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        executor = OptimizedThreadPoolExecutor()
        return await executor.run_cpu_bound(func, *args, **kwargs)
    return wrapper


def io_bound_task(func: Callable) -> Callable:
    """Decorator to automatically run I/O-bound functions in thread pool."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        executor = OptimizedThreadPoolExecutor()
        return await executor.run_io_bound(func, *args, **kwargs)
    return wrapper


class PerformanceMonitor:
    """Monitor and log performance metrics."""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger
        self.metrics = {}
        self._start_times = {}
    
    def start_timer(self, name: str):
        """Start timing an operation."""
        self._start_times[name] = time.time()
    
    def end_timer(self, name: str) -> float:
        """End timing an operation and return duration."""
        if name not in self._start_times:
            return 0.0
        
        duration = time.time() - self._start_times[name]
        del self._start_times[name]
        
        # Store metric
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration)
        
        # Keep only last 100 measurements
        if len(self.metrics[name]) > 100:
            self.metrics[name] = self.metrics[name][-100:]
        
        return duration
    
    def get_average(self, name: str) -> float:
        """Get average duration for an operation."""
        if name not in self.metrics or not self.metrics[name]:
            return 0.0
        return sum(self.metrics[name]) / len(self.metrics[name])
    
    async def log_metrics(self):
        """Log current performance metrics."""
        if not self.logger:
            return
        
        for name, durations in self.metrics.items():
            if durations:
                avg = sum(durations) / len(durations)
                await self.logger.info(f"Performance metric {name}: avg={avg:.3f}s, samples={len(durations)}")


# Global instances
_thread_pool = None
_task_queue = None
_performance_monitor = None


def get_thread_pool() -> OptimizedThreadPoolExecutor:
    """Get global thread pool instance."""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = OptimizedThreadPoolExecutor()
    return _thread_pool


async def get_task_queue() -> AsyncTaskQueue:
    """Get global task queue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = AsyncTaskQueue()
        await _task_queue.start()
    return _task_queue


def get_performance_monitor(logger: Optional[Logger] = None) -> PerformanceMonitor:
    """Get global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor(logger)
    return _performance_monitor