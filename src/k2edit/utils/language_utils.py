"""Language detection utilities for K2Edit

Pure functions for detecting programming languages from various sources.
"""

import os
from pathlib import Path
from typing import Dict, List, Any


def detect_language_by_extension(extension: str) -> str:
    """Detect language based on file extension.
    
    Args:
        extension: File extension (e.g., '.py', '.js')
        
    Returns:
        Language name or 'unknown' if not recognized
    """
    extension = extension.lower()
    
    # Language configuration mapping
    ext_to_language = {
        '.py': 'python',
        '.js': 'javascript', 
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.xml': 'xml',
        '.sql': 'sql',
        '.sh': 'shell',
        '.md': 'markdown',
        '.nim': 'nim'
    }
    
    return ext_to_language.get(extension, 'unknown')


def detect_language_from_filename(filename: str) -> str:
    """Detect programming language from filename.
    
    Args:
        filename: Full filename or path
        
    Returns:
        Language name or 'unknown' if not recognized
    """
    if not filename:
        return 'unknown'
        
    _, ext = os.path.splitext(filename)
    return detect_language_by_extension(ext)


def detect_language_from_file_path(file_path: str) -> str:
    """Detect programming language from file path for display purposes.
    
    Args:
        file_path: Full file path
        
    Returns:
        Capitalized language name for display or empty string if not recognized
    """
    if not file_path:
        return ""
    
    # Display-friendly language mapping
    ext_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.jsx': 'JavaScript',
        '.tsx': 'TypeScript',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.go': 'Go',
        '.rs': 'Rust',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.html': 'HTML',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.json': 'JSON',
        '.yaml': 'YAML',
        '.yml': 'YAML',
        '.xml': 'XML',
        '.sql': 'SQL',
        '.sh': 'Shell',
        '.md': 'Markdown',
        '.nim': 'Nim'
    }
    
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, "")


def detect_project_language(project_root: str) -> str:
    """Detect the primary language of a project.
    
    Args:
        project_root: Path to project root directory
        
    Returns:
        Primary language name or 'unknown' if not detected
    """
    root = Path(project_root)
    
    # Common language indicators (config files and extensions)
    language_indicators = {
        "python": ["requirements.txt", "setup.py", "pyproject.toml", ".py"],
        "javascript": ["package.json", "yarn.lock", ".js", ".ts"],
        "go": ["go.mod", "go.sum", ".go"],
        "rust": ["Cargo.toml", "Cargo.lock", ".rs"],
        "java": ["pom.xml", "build.gradle", ".java"],
        "cpp": ["CMakeLists.txt", "Makefile", ".cpp", ".h"],
        "nim": ["nim.cfg", ".nim", ".nims"]
    }
    
    for lang, indicators in language_indicators.items():
        for indicator in indicators:
            if any(root.rglob(f"*{indicator}")):
                return lang
                
    return "unknown"


def get_supported_extensions() -> List[str]:
    """Get all supported file extensions.
    
    Returns:
        List of supported file extensions
    """
    extensions = [
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
        '.go', '.rs', '.rb', '.php', '.html', '.css', '.scss',
        '.json', '.yaml', '.yml', '.xml', '.sql', '.sh', '.md', '.nim'
    ]
    return extensions


def get_supported_languages() -> List[str]:
    """Get all supported programming languages.
    
    Returns:
        List of supported language names
    """
    languages = [
        'python', 'javascript', 'typescript', 'java', 'cpp', 'c',
        'go', 'rust', 'ruby', 'php', 'html', 'css', 'scss',
        'json', 'yaml', 'xml', 'sql', 'shell', 'markdown', 'nim'
    ]
    return languages


def is_supported_language(language: str) -> bool:
    """Check if a language is supported.
    
    Args:
        language: Language name to check
        
    Returns:
        True if language is supported, False otherwise
    """
    return language.lower() in get_supported_languages()


def is_supported_extension(extension: str) -> bool:
    """Check if a file extension is supported.
    
    Args:
        extension: File extension to check (e.g., '.py')
        
    Returns:
        True if extension is supported, False otherwise
    """
    return extension.lower() in get_supported_extensions()