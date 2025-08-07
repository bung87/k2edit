"""Utility modules for K2Edit."""

from .error_handler import (
    ErrorHandler,
    K2EditError,
    FileOperationError,
    AgentSystemError,
    LSPError,
    ErrorSeverity,
    create_error_handler
)

from .config import (
    K2EditConfig,
    UIConfig,
    AgentConfig,
    LSPConfig,
    FileConfig,
    LoggingConfig,
    get_config,
    set_config,
    load_config_from_file
)

from .initialization import (
    AgentInitializer,
    FileInitializer,
    create_agent_initializer,
    create_file_initializer
)

from .language_utils import (
    detect_language_by_extension,
    detect_language_from_filename,
    detect_language_from_file_path,
    detect_project_language,
    get_supported_extensions,
    get_supported_languages,
    is_supported_language,
    is_supported_extension
)

__all__ = [
    # Error handling
    "ErrorHandler",
    "K2EditError",
    "FileOperationError",
    "AgentSystemError",
    "LSPError",
    "ErrorSeverity",
    "create_error_handler",
    
    # Configuration
    "K2EditConfig",
    "UIConfig",
    "AgentConfig",
    "LSPConfig",
    "FileConfig",
    "LoggingConfig",
    "get_config",
    "set_config",
    "load_config_from_file",
    
    # Initialization
    "AgentInitializer",
    "FileInitializer",
    "create_agent_initializer",
    "create_file_initializer",
    
    # Language utilities
    "detect_language_by_extension",
    "detect_language_from_filename",
    "detect_language_from_file_path",
    "detect_project_language",
    "get_supported_extensions",
    "get_supported_languages",
    "is_supported_language",
    "is_supported_extension",
]