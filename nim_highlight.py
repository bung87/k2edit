#!/usr/bin/env python3
"""Nim syntax highlighting module for Textual."""

from typing import Optional, Tuple

def get_nim_language() -> Optional[object]:
    """Get the Nim language object from tree-sitter-nim."""
    try:
        import tree_sitter_nim
        return tree_sitter_nim.language()
    except ImportError:
        return None

def get_nim_highlight_query() -> str:
    """Get the Nim syntax highlighting query."""
    return """
    ; Comments
    (comment) @comment
    
    ; Strings
    (string_literal) @string
    (raw_string_literal) @string
    
    ; Numbers
    (int_literal) @number
    (float_literal) @number
    
    ; Keywords
    (proc) @keyword
    (func) @keyword
    (template) @keyword
    (macro) @keyword
    (type) @keyword
    (var) @keyword
    (let) @keyword
    (const) @keyword
    (if) @keyword
    (elif) @keyword
    (else) @keyword
    (for) @keyword
    (while) @keyword
    (try) @keyword
    (except) @keyword
    (finally) @keyword
    (import) @keyword
    (export) @keyword
    (from) @keyword
    (include) @keyword
    (echo) @keyword
    (return) @keyword
    (result) @keyword
    (discard) @keyword
    (break) @keyword
    (continue) @keyword
    (when) @keyword
    (case) @keyword
    (of) @keyword
    (block) @keyword
    (defer) @keyword
    (static) @keyword
    (const) @keyword
    (nil) @keyword
    (true) @keyword
    (false) @keyword
    (addr) @keyword
    (as) @keyword
    (asm) @keyword
    (atomic) @keyword
    (bind) @keyword
    (cast) @keyword
    (concept) @keyword
    (converter) @keyword
    (distinct) @keyword
    (enum) @keyword
    (except) @keyword
    (finally) @keyword
    (iterator) @keyword
    (method) @keyword
    (mixin) @keyword
    (mod) @keyword
    (not) @keyword
    (notin) @keyword
    (object) @keyword
    (of) @keyword
    (out) @keyword
    (ptr) @keyword
    (raise) @keyword
    (ref) @keyword
    (shl) @keyword
    (shr) @keyword
    (tuple) @keyword
    (using) @keyword
    (with) @keyword
    (without) @keyword
    (xor) @keyword
    (yield) @keyword
    
    ; Identifiers
    (identifier) @variable
    (proc_name) @function
    (func_name) @function
    (template_name) @function
    (macro_name) @function
    (type_name) @type
    (variable_name) @variable
    (field_name) @variable
    
    ; Operators
    (operator) @operator
    (assignment) @operator
    (comparison) @operator
    (arithmetic_operator) @operator
    (logical_operator) @operator
    (bitwise_operator) @operator
    
    ; Punctuation
    (punctuation) @punctuation
    (delimiter) @punctuation
    (dot) @punctuation
    (comma) @punctuation
    (semicolon) @punctuation
    (colon) @punctuation
    
    ; Special constructs
    (pragma) @preprocessor
    (pragma_statement) @preprocessor
    (compiler_directive) @preprocessor
    
    ; Type annotations
    (type_annotation) @type
    (generic_parameter) @type
    (generic_argument) @type
    
    ; Function calls
    (function_call) @function
    (method_call) @function
    
    ; Control flow
    (if_statement) @keyword
    (elif_statement) @keyword
    (else_statement) @keyword
    (for_statement) @keyword
    (while_statement) @keyword
    (try_statement) @keyword
    (except_statement) @keyword
    (finally_statement) @keyword
    (case_statement) @keyword
    (of_statement) @keyword
    (when_statement) @keyword
    (block_statement) @keyword
    (defer_statement) @keyword
    
    ; Declarations
    (proc_declaration) @keyword
    (func_declaration) @keyword
    (template_declaration) @keyword
    (macro_declaration) @keyword
    (type_declaration) @keyword
    (var_declaration) @keyword
    (let_declaration) @keyword
    (const_declaration) @keyword
    (import_statement) @keyword
    (export_statement) @keyword
    (from_statement) @keyword
    (include_statement) @keyword
    """

def register_nim_language(text_area) -> bool:
    """Register Nim language with a Textual TextArea.
    
    Args:
        text_area: The TextArea instance to register the language with
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    try:
        nim_language = get_nim_language()
        if nim_language is None:
            return False
            
        nim_highlight_query = get_nim_highlight_query()
        
        # Register Nim language with the TextArea instance
        text_area.register_language('nim', nim_language, nim_highlight_query)
        
        return True
        
    except Exception as e:
        # Log error if logger is available
        if hasattr(text_area, '_app_instance') and text_area._app_instance:
            if hasattr(text_area._app_instance, 'logger'):
                text_area._app_instance.logger.error(f"NIM HIGHLIGHT: Failed to register Nim language: {e}")
        return False

def is_nim_available() -> bool:
    """Check if tree-sitter-nim is available."""
    try:
        import tree_sitter_nim
        return True
    except ImportError:
        return False 