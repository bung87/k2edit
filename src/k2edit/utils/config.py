"""Configuration management for K2Edit."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class UIConfig:
    """UI-related configuration."""
    hover_delay_ms: int = 500
    status_update_interval_s: float = 1.0
    agent_init_delay_s: float = 2.0
    output_panel_scroll_delay_ms: int = 100


@dataclass
class AgentConfig:
    """Agent system configuration."""
    initialization_timeout_s: int = 30
    query_timeout_s: int = 60
    max_context_files: int = 50
    max_file_size_mb: int = 10


@dataclass
class LSPConfig:
    """LSP client configuration."""
    connection_timeout_s: int = 10
    response_timeout_s: int = 5
    max_diagnostics_per_file: int = 100
    hover_timeout_s: int = 2


@dataclass
class FileConfig:
    """File operation configuration."""
    max_file_size_mb: int = 50
    backup_enabled: bool = True
    auto_save_interval_s: int = 300  # 5 minutes
    encoding: str = "utf-8"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    max_file_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class K2EditConfig:
    """Main configuration class for K2Edit."""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.ui = UIConfig()
        self.agent = AgentConfig()
        self.lsp = LSPConfig()
        self.file = FileConfig()
        self.logging = LoggingConfig()
        
        if config_file and config_file.exists():
            self._load_from_file(config_file)
    
    def _load_from_file(self, config_file: Path):
        """Load configuration from a file (JSON/YAML)."""
        # TODO: Implement file-based configuration loading
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "ui": self.ui.__dict__,
            "agent": self.agent.__dict__,
            "lsp": self.lsp.__dict__,
            "file": self.file.__dict__,
            "logging": self.logging.__dict__
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'K2EditConfig':
        """Create configuration from dictionary."""
        config = cls()
        
        if "ui" in data:
            config.ui = UIConfig(**data["ui"])
        if "agent" in data:
            config.agent = AgentConfig(**data["agent"])
        if "lsp" in data:
            config.lsp = LSPConfig(**data["lsp"])
        if "file" in data:
            config.file = FileConfig(**data["file"])
        if "logging" in data:
            config.logging = LoggingConfig(**data["logging"])
        
        return config


# Global configuration instance
_config: Optional[K2EditConfig] = None


def get_config() -> K2EditConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = K2EditConfig()
    return _config


def set_config(config: K2EditConfig):
    """Set the global configuration instance."""
    global _config
    _config = config


def load_config_from_file(config_file: Path) -> K2EditConfig:
    """Load configuration from file and set as global."""
    config = K2EditConfig(config_file)
    set_config(config)
    return config