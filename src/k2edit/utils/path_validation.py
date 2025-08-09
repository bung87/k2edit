"""Path validation utilities for K2Edit."""

from pathlib import Path
from typing import Optional, Tuple


class PathValidationError(Exception):
    """Exception raised for path validation errors."""
    pass


def validate_file_path(file_path: str, allow_create: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate a file path for opening/loading operations.
    
    Args:
        file_path: The file path to validate
        allow_create: Whether to allow non-existent files (for creation)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if not file_path or not file_path.strip():
            return False, "File path cannot be empty"
            
        path = Path(file_path)
        
        # Check if path exists
        if not path.exists():
            if allow_create:
                # Check if parent directory exists or can be created
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return True, None
                except (OSError, PermissionError) as e:
                    return False, f"Cannot create parent directory: {e}"
            else:
                return False, f"File or directory does not exist: {file_path}"
        
        # Check if it's a directory when we expect a file
        if path.is_dir():
            return False, f"Path is a directory, not a file: {file_path}"
            
        # Check if file is readable
        if not path.is_file():
            return False, f"Path exists but is not a regular file: {file_path}"
            
        try:
            # Test read access
            with open(path, 'r', encoding='utf-8') as f:
                pass
        except (PermissionError, OSError) as e:
            return False, f"Cannot read file: {e}"
            
        return True, None
        
    except Exception as e:
        return False, f"Path validation error: {e}"


def validate_directory_path(dir_path: str, allow_create: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate a directory path.
    
    Args:
        dir_path: The directory path to validate
        allow_create: Whether to allow non-existent directories (for creation)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if not dir_path or not dir_path.strip():
            return False, "Directory path cannot be empty"
            
        path = Path(dir_path)
        
        # Check if path exists
        if not path.exists():
            if allow_create:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    return True, None
                except (OSError, PermissionError) as e:
                    return False, f"Cannot create directory: {e}"
            else:
                return False, f"Directory does not exist: {dir_path}"
        
        # Check if it's actually a directory
        if not path.is_dir():
            return False, f"Path exists but is not a directory: {dir_path}"
            
        # Check if directory is accessible
        try:
            list(path.iterdir())
        except (PermissionError, OSError) as e:
            return False, f"Cannot access directory: {e}"
            
        return True, None
        
    except Exception as e:
        return False, f"Directory validation error: {e}"


def validate_path_for_save(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a file path for saving operations.
    
    Args:
        file_path: The file path to validate for saving
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if not file_path or not file_path.strip():
            return False, "File path cannot be empty"
            
        path = Path(file_path)
        
        # Ensure parent directory exists or can be created
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            return False, f"Cannot create parent directory: {e}"
        
        # If file exists, check if it's writable
        if path.exists():
            if path.is_dir():
                return False, f"Path is a directory, cannot save as file: {file_path}"
            
            try:
                # Test write access
                with open(path, 'a', encoding='utf-8') as f:
                    pass
            except (PermissionError, OSError) as e:
                return False, f"Cannot write to file: {e}"
        else:
            # Test if we can create the file
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    pass
                path.unlink()  # Remove the test file
            except (PermissionError, OSError) as e:
                return False, f"Cannot create file: {e}"
                
        return True, None
        
    except Exception as e:
        return False, f"Save path validation error: {e}"


def safe_resolve_path(path_str: str) -> Optional[Path]:
    """
    Safely resolve a path string to a Path object.
    
    Args:
        path_str: The path string to resolve
        
    Returns:
        Resolved Path object or None if invalid
    """
    try:
        if not path_str or not path_str.strip():
            return None
        return Path(path_str).resolve()
    except Exception:
        return None