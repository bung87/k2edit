"""Path validation utilities for K2Edit."""

import asyncio
import aiofiles
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
            
        # Note: File access test will be done by caller using async operations
        # This validation focuses on path structure and existence
            
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
        
        # If file exists, check if it's a directory
        if path.exists():
            if path.is_dir():
                return False, f"Path is a directory, cannot save as file: {file_path}"
        
        # Note: Write access test will be done by caller using async operations
        # This validation focuses on path structure and parent directory creation
                
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


async def async_validate_file_path(file_path: str, allow_create: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Async version of validate_file_path with actual file access testing.
    
    Args:
        file_path: The file path to validate
        allow_create: Whether to allow non-existent files (for creation)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # First do basic path validation
        is_valid, error = validate_file_path(file_path, allow_create)
        if not is_valid:
            return is_valid, error
            
        path = Path(file_path)
        
        # Test actual file access asynchronously if file exists
        if path.exists() and path.is_file():
            try:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    # Just test if we can open it
                    pass
            except (PermissionError, OSError) as e:
                return False, f"Cannot read file: {e}"
                
        return True, None
        
    except Exception as e:
        return False, f"Async path validation error: {e}"


async def async_validate_path_for_save(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Async version of validate_path_for_save with actual file access testing.
    
    Args:
        file_path: The file path to validate for saving
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # First do basic path validation
        is_valid, error = validate_path_for_save(file_path)
        if not is_valid:
            return is_valid, error
            
        path = Path(file_path)
        
        # Test actual file access asynchronously
        if path.exists():
            try:
                # Test write access by opening in append mode
                async with aiofiles.open(path, 'a', encoding='utf-8') as f:
                    pass
            except (PermissionError, OSError) as e:
                return False, f"Cannot write to file: {e}"
        else:
            try:
                # Test if we can create the file
                async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                    pass
                # Use asyncio.to_thread for file deletion to avoid blocking
                await asyncio.to_thread(path.unlink)
            except (PermissionError, OSError) as e:
                return False, f"Cannot create file: {e}"
                
        return True, None
        
    except Exception as e:
        return False, f"Async save path validation error: {e}"