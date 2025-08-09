"""Utility modules for K2Edit."""

# Error handler removed - using basic exception handling

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

# Initialization imports moved to avoid circular dependencies
# Import these directly when needed:
# from .initialization import AgentInitializer, FileInitializer

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
    
    # Initialization - import directly from .initialization when needed
    
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