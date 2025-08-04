#!/usr/bin/env python3
"""Nim syntax highlighting module for Textual."""

import os
from typing import Optional

def get_nim_language() -> Optional[object]:
    """Get the Nim language object from tree-sitter-nim."""
    try:
        import tree_sitter
        import tree_sitter_nim
        
        # Get the language pointer from tree-sitter-nim
        language_ptr = tree_sitter_nim.language()
        
        return tree_sitter.Language(language_ptr)
            
    except ImportError:
        return None

def get_nim_highlight_query() -> str:
    """Get the Nim syntax highlighting query from the official tree-sitter-nim package."""

    import tree_sitter_nim
    # Get the path to the queries directory in the tree-sitter-nim package
    package_dir = os.path.dirname(tree_sitter_nim.__file__)
    highlights_file = os.path.join(package_dir, "queries", "highlights.scm")
    
    # Read the official highlights.scm file
    with open(highlights_file, 'r', encoding='utf-8') as f:
        return f.read()

def register_nim_language(text_area) -> bool:
    """Register Nim language with a Textual TextArea.
    
    Args:
        text_area: The TextArea instance to register the language with
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    nim_language = get_nim_language()
    if nim_language is None:
        return False
        
    nim_highlight_query = get_nim_highlight_query()
    
    # Register Nim language with the TextArea instance
    text_area.register_language('nim', nim_language, nim_highlight_query)
    
    return True

def is_nim_available() -> bool:
    """Check if tree-sitter-nim is available."""
    try:
        import tree_sitter_nim
        return True
    except ImportError:
        return False 