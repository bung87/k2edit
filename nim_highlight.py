#!/usr/bin/env python3
"""Nim syntax highlighting module for Textual."""

from typing import Optional, Tuple

def get_nim_language() -> Optional[object]:
    """Get the Nim language object from tree-sitter-nim."""
    try:
        import tree_sitter
        import tree_sitter_nim
        
        # Get the language pointer from tree-sitter-nim
        language_ptr = tree_sitter_nim.language()
        
        # Wrap it in a tree_sitter.Language object
        # Try the newer API first (with name parameter)
        try:
            return tree_sitter.Language(language_ptr, "nim")
        except TypeError:
            # Fall back to older API (single argument)
            return tree_sitter.Language(language_ptr)
            
    except ImportError:
        return None

def get_nim_highlight_query() -> str:
    """Get the Nim syntax highlighting query."""
    return """
    ; Comments
    (comment) @comment
    
    ; Strings
    (raw_string_literal) @string
    
    ; Numbers
    (float_literal) @number
    
    ; Control flow
    (if) @keyword
    (for) @keyword
    (while) @keyword
    
    ; Identifiers
    (identifier) @variable
    """

def register_nim_language(text_area) -> bool:
    """Register Nim language with a Textual TextArea.
    
    Args:
        text_area: The TextArea instance to register the language with
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    try:
        import tree_sitter
        
        nim_language = get_nim_language()
        if nim_language is None:
            return False
            
        nim_highlight_query = get_nim_highlight_query()
        
        # Test the query first to make sure it's valid
        try:
            query = tree_sitter.Query(nim_language, nim_highlight_query)
        except Exception as e:
            # If query fails, use a minimal working query
            minimal_query = """
            (comment) @comment
            (identifier) @variable
            """
            query = tree_sitter.Query(nim_language, minimal_query)
        
        # Register Nim language with the TextArea instance
        text_area.register_language('nim', nim_language, nim_highlight_query)
        
        return True
        
    except Exception as e:
        # Note: Logging removed to avoid async logger issues during __init__
        # The error will be handled by the calling code
        return False

def is_nim_available() -> bool:
    """Check if tree-sitter-nim is available."""
    try:
        import tree_sitter_nim
        return True
    except ImportError:
        return False 