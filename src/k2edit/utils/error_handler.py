"""Standardized error handling utilities for K2Edit."""

import asyncio
import traceback
from typing import Optional, Callable, Any, Dict
from functools import wraps
from aiologger import Logger


class ErrorSeverity:
    """Error severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class K2EditError(Exception):
    """Base exception class for K2Edit errors."""
    
    def __init__(self, message: str, severity: str = ErrorSeverity.ERROR, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.context = context or {}


class FileOperationError(K2EditError):
    """Error during file operations."""
    pass


class AgentSystemError(K2EditError):
    """Error in the agentic system."""
    pass


class LSPError(K2EditError):
    """Error in LSP operations."""
    pass


class ErrorHandler:
    """Centralized error handling for K2Edit."""
    
    def __init__(self, logger: Logger, output_panel=None):
        self.logger = logger
        self.output_panel = output_panel
        self._error_callbacks = []
    
    def set_output_panel(self, output_panel):
        """Set the output panel for user notifications."""
        self.output_panel = output_panel
    
    def add_error_callback(self, callback: Callable[[K2EditError], None]):
        """Add a callback to be called when errors occur."""
        self._error_callbacks.append(callback)
    
    async def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                          user_message: Optional[str] = None) -> None:
        """Handle an error with appropriate logging and user notification."""
        
        # Convert to K2EditError if needed
        if isinstance(error, K2EditError):
            k2_error = error
        else:
            k2_error = K2EditError(
                str(error),
                severity=ErrorSeverity.ERROR,
                context=context or {}
            )
        
        # Log the error
        await self._log_error(k2_error)
        
        # Notify user if output panel is available
        if self.output_panel and user_message:
            self.output_panel.add_error(user_message)
        
        # Call error callbacks
        for callback in self._error_callbacks:
            try:
                callback(k2_error)
            except Exception as cb_error:
                await self.logger.error(f"Error in error callback: {cb_error}")
    
    async def _log_error(self, error: K2EditError) -> None:
        """Log an error with appropriate severity."""
        log_message = f"{error.message}"
        if error.context:
            log_message += f" Context: {error.context}"
        
        if error.severity == ErrorSeverity.DEBUG:
            await self.logger.debug(log_message)
        elif error.severity == ErrorSeverity.INFO:
            await self.logger.info(log_message)
        elif error.severity == ErrorSeverity.WARNING:
            await self.logger.warning(log_message)
        elif error.severity == ErrorSeverity.ERROR:
            await self.logger.error(log_message)
        elif error.severity == ErrorSeverity.CRITICAL:
            await self.logger.critical(log_message)
    
    def with_error_handling(self, user_message: Optional[str] = None, 
                           reraise: bool = False):
        """Decorator for automatic error handling."""
        def decorator(func):
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        await self.handle_error(e, user_message=user_message)
                        if reraise:
                            raise
                        return None
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        # For sync functions, we need to handle async logging differently
                        asyncio.create_task(self.handle_error(e, user_message=user_message))
                        if reraise:
                            raise
                        return None
                return sync_wrapper
        return decorator


def create_error_handler(logger: Logger, output_panel=None) -> ErrorHandler:
    """Factory function to create an error handler."""
    return ErrorHandler(logger, output_panel)