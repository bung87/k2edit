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


def setup_logging(log_level: str = "DEBUG") -> Logger:
    """Setup logging configuration with both file and Textual handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
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
        interval=1,
        backup_count=7,
        encoding="utf-8"
    )
    console_handler = AsyncStreamHandler()
    
    # Set formatter
    formatter = Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.formatter = formatter
    console_handler.formatter = formatter
    
    # Add handlers to logger
    logger.add_handler(file_handler)
    # logger.add_handler(console_handler)
    
    return logger


def get_logger(name: str = None) -> Logger:
    """Get a logger instance with the specified name.
    
    Args:
        name: Logger name (optional)
        
    Returns:
        Logger instance with handlers configured
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename
    log_file = log_dir / "k2edit.log"
    
    # Configure logger
    logger = Logger(name=name or "k2edit")
    
    # Create handlers
    file_handler = AsyncTimedRotatingFileHandler(
        filename=str(log_file),
        interval=1,
        backup_count=7,
        encoding="utf-8"
    )
    
    # Set formatter
    formatter = Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.formatter = formatter
    
    # Add handler to logger
    logger.add_handler(file_handler)
    
    return logger 