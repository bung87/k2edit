#!/usr/bin/env python3
"""
Shared logging configuration for K2Edit application.
"""

import os
from pathlib import Path
from aiologger import Logger
from aiologger.levels import LogLevel
from aiologger.handlers.files import AsyncTimedRotatingFileHandler
from aiologger.handlers.streams import AsyncStreamHandler
from aiologger.formatters.base import Formatter


# Global logger instance
_global_logger = None


def setup_logging(log_level: str = "DEBUG") -> Logger:
    """Setup logging configuration with both file and Textual handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    global _global_logger
    
    if _global_logger is not None:
        return _global_logger
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    log_file = log_dir / "k2edit.log"
    
    # Configure root logger
    logger = Logger(name="k2edit")
    
    # Set log level
    level = LogLevel.DEBUG if log_level.upper() == "DEBUG" else \
            LogLevel.INFO if log_level.upper() == "INFO" else \
            LogLevel.WARNING if log_level.upper() == "WARNING" else \
            LogLevel.ERROR if log_level.upper() == "ERROR" else \
            LogLevel.CRITICAL
    
    # Create handlers
    file_handler = AsyncTimedRotatingFileHandler(
        filename=str(log_file),
        when='D',
        interval=1,
        backup_count=7,
        encoding="utf-8"
    )
    # console_handler = AsyncStreamHandler()
    
    # Set formatter
    formatter = Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.formatter = formatter
    # console_handler.formatter = formatter
    
    # Add handlers to logger
    logger.add_handler(file_handler)
    # logger.add_handler(console_handler)
    
    _global_logger = logger
    return _global_logger


def get_logger(name: str = None) -> Logger:
    """Get the singleton logger instance.
    
    Args:
        name: Logger name (ignored for singleton instance)
        
    Returns:
        Singleton logger instance with handlers configured
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = setup_logging()
    
    return _global_logger