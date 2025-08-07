"""Language Server Configurations for K2Edit Agentic System
Defines configurations for different language servers"""

import sys
from typing import Dict, List, Any
from ..utils.language_utils import detect_language_by_extension as _detect_language_by_extension


class LanguageConfigs:
    """Language server configurations for different programming languages"""
    
    @staticmethod
    def get_configs() -> Dict[str, Dict[str, Any]]:
        """Get all language server configurations"""
        return {
            "python": {
                "command": [sys.executable, "-m", "pylsp"],
                "extensions": [".py"],
                "settings": {
                    "pylsp": {
                        "plugins": {
                            "pycodestyle": {"enabled": True},
                            "pyflakes": {"enabled": True},
                            "mccabe": {"enabled": True}
                        }
                    }
                },
                "skip_patterns": [
                    "venv/", "env/", ".venv/", ".env/", "virtualenv/",
                    "__pycache__/", ".pytest_cache/", ".mypy_cache/",
                    ".coverage", "site-packages/", "dist-packages/",
                    "lib/python", "lib64/python", "include/python",
                    "Scripts/", "bin/", "node_modules/", ".git",
                    ".hg", ".svn", ".tox", ".eggs", "build", "dist",
                    "*.egg-info", ".cache", ".local", ".virtualenvs"
                ]
            },
            "javascript": {
                "command": ["typescript-language-server", "--stdio"],
                "extensions": [".js", ".ts", ".jsx", ".tsx"],
                "settings": {},
                "skip_patterns": ["node_modules/", ".git", "dist/", "build/"]
            },
            "typescript": {
                "command": ["typescript-language-server", "--stdio"],
                "extensions": [".ts", ".tsx"],
                "settings": {},
                "skip_patterns": ["node_modules/", ".git", "dist/", "build/"]
            },
            "go": {
                "command": ["gopls"],
                "extensions": [".go"],
                "settings": {},
                "skip_patterns": ["vendor/", ".git", "bin/", "pkg/"]
            },
            "rust": {
                "command": ["rust-analyzer"],
                "extensions": [".rs"],
                "settings": {},
                "skip_patterns": ["target/", ".git", ".cargo/"]
            },
            "nim": {
                "command": ["nimlsp"],
                "extensions": [".nim"],
                "settings": {},
                "skip_patterns": ["nimcache/", ".git", "bin/"]
            }
        }
    
    @staticmethod
    def get_config(language: str) -> Dict[str, Any]:
        """Get configuration for a specific language"""
        configs = LanguageConfigs.get_configs()
        return configs.get(language, {})
    
    @staticmethod
    def detect_language_by_extension(extension: str) -> str:
        """Detect language based on file extension"""
        return _detect_language_by_extension(extension)
    
    @staticmethod
    def get_supported_extensions() -> List[str]:
        """Get all supported file extensions"""
        configs = LanguageConfigs.get_configs()
        extensions = []
        
        for config in configs.values():
            extensions.extend(config["extensions"])
        
        return list(set(extensions))
    
    @staticmethod
    def get_supported_languages() -> List[str]:
        """Get all supported programming languages"""
        configs = LanguageConfigs.get_configs()
        return list(configs.keys())