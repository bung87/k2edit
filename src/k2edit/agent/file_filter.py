"""
File Filter for K2Edit Agentic System
Handles file filtering based on language-specific patterns and project structure
"""

from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from aiologger import Logger


class FileFilter:
    """Handles file filtering based on language-specific patterns"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def should_skip_file(self, file_path: Path, language: str, project_root: Path) -> bool:
        """Check if a file should be skipped based on language-specific patterns"""
        try:
            # Convert to absolute path for reliable comparison
            abs_path = file_path.resolve()
            project_root = project_root.resolve()
            
            # Check if file is within the project root
            if not abs_path.is_relative_to(project_root):
                return True
            
            # Get skip patterns for the language
            skip_patterns = self._get_skip_patterns(language)
            
            # Check if any part of the path matches skip patterns
            path_str = str(abs_path)
            for pattern in skip_patterns:
                if pattern in path_str:
                    return True
            
            # Check for specific directory patterns
            return self._check_directory_patterns(abs_path)
            
        except Exception as e:
            # If there's any error in checking, log it but don't skip the file
            # This ensures we don't accidentally skip important files
            return False
    
    def _get_skip_patterns(self, language: str) -> List[str]:
        """Get skip patterns for a specific language"""
        from .language_configs import LanguageConfigs
        
        config = LanguageConfigs.get_config(language)
        return config.get("skip_patterns", [])
    
    def _check_directory_patterns(self, file_path: Path) -> bool:
        """Check for common directory patterns that should be skipped"""
        skip_dirs = {
            "node_modules", ".git", ".hg", ".svn", 
            ".tox", ".eggs", "build", "dist",
            "__pycache__", ".pytest_cache", ".mypy_cache",
            ".coverage", ".cache", ".local", ".virtualenvs"
        }
        
        # Check each directory in the path
        for part in file_path.parts:
            if part in skip_dirs:
                return True
            
            # Check for egg-info patterns
            if part.endswith('.egg-info'):
                return True
        
        return False
    
    def get_project_files(self, project_root: Path, language: str) -> List[Path]:
        """Get all relevant files for a language in the project"""
        from .language_configs import LanguageConfigs
        
        config = LanguageConfigs.get_config(language)
        extensions = config.get("extensions", [])
        
        if not extensions:
            return []
        
        # Convert extensions to set for faster lookup
        ext_set = set(extensions)
        files = []
        skip_patterns = self._get_skip_patterns(language)
        
        # Manual directory traversal with early skip pattern checking
        def _traverse_directory(dir_path: Path):
            try:
                for item in dir_path.iterdir():
                    # Check skip patterns early for directories
                    if item.is_dir():
                        # Skip if directory matches skip patterns
                        dir_str = str(item)
                        should_skip = False
                        for pattern in skip_patterns:
                            if pattern in dir_str:
                                should_skip = True
                                break
                        
                        if not should_skip and not self._check_directory_patterns(item):
                            _traverse_directory(item)
                    
                    elif item.is_file() and item.suffix in ext_set:
                        if not self.should_skip_file(item, language, project_root):
                            files.append(item)
            except (PermissionError, OSError):
                # Skip directories we can't access
                pass
        
        _traverse_directory(project_root)
        return files
    
    def count_filtered_files(self, project_root: Path, language: str) -> Dict[str, int]:
        """Count files that would be filtered out for a language"""
        from .language_configs import LanguageConfigs
        
        config = LanguageConfigs.get_config(language)
        extensions = config.get("extensions", [])
        
        if not extensions:
            return {"total": 0, "filtered": 0, "included": 0}
        
        # Convert extensions to set for faster lookup
        ext_set = set(extensions)
        total_files = 0
        included_count = 0
        skip_patterns = self._get_skip_patterns(language)
        
        # Manual directory traversal with early skip pattern checking
        def _traverse_directory(dir_path: Path):
            nonlocal total_files, included_count
            try:
                for item in dir_path.iterdir():
                    # Check skip patterns early for directories
                    if item.is_dir():
                        # Skip if directory matches skip patterns
                        dir_str = str(item)
                        should_skip = False
                        for pattern in skip_patterns:
                            if pattern in dir_str:
                                should_skip = True
                                break
                        
                        if not should_skip and not self._check_directory_patterns(item):
                            _traverse_directory(item)
                    
                    elif item.is_file() and item.suffix in ext_set:
                        total_files += 1
                        if not self.should_skip_file(item, language, project_root):
                            included_count += 1
            except (PermissionError, OSError):
                # Skip directories we can't access
                pass
        
        _traverse_directory(project_root)
        filtered_count = total_files - included_count
        
        return {
            "total": total_files,
            "filtered": filtered_count,
            "included": included_count
        }
    
    def detect_project_language(self, project_root: Path) -> str:
        """Detect the primary language of the project"""
        return detect_project_language(str(project_root))
    
    def get_file_info(self, file_path: Path) -> Dict[str, any]:
        """Get basic file information"""
        try:
            stat = file_path.stat()
            return {
                "path": str(file_path),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "exists": file_path.exists(),
                "is_file": file_path.is_file()
            }
        except Exception as e:
            return {
                "path": str(file_path),
                "error": str(e),
                "exists": False
            }