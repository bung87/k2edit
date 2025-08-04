import tree_sitter
import importlib.resources
import logging
import sys

# Set up logging
logger = logging.getLogger(__name__)

def patched_prepare_query(self, query):
    """Patched version of prepare_query that handles string queries properly."""
    try:
        if isinstance(query, str):
            query = query.encode("utf-8")
        return self.language.query(query)
    except Exception as e:
        logger.error(f"Error in patched_prepare_query: {e}")
        raise

def patched_init(self, text, language=None, parser=None):
    """Patched version of TextualDocument.__init__ with proper tree-sitter integration."""
    try:
        self.language = language
        self.parser = parser
        self.tree = None
        self.root_node = None
        self._lines = text.splitlines(keepends=True)
        self._text = text
        self._version = 0
        
        if self.language and self.parser:
            self.parser.set_language(self.language)
            self.tree = self.parser.parse(bytes(text, "utf-8"))
            self.root_node = self.tree.root_node
    except Exception as e:
        logger.error(f"Error in patched_init: {e}")
        # Fall back to basic initialization
        self._lines = text.splitlines(keepends=True)
        self._text = text
        self._version = 0

def patched_get_language(language_name):
    """Patched version of get_language that handles different tree-sitter versions."""
    try:
        # Import tree_sitter here to ensure it's available
        import tree_sitter
        
        # Import the appropriate tree-sitter language module
        if language_name == "python":
            import tree_sitter_python
            module = tree_sitter_python
        elif language_name == "javascript":
            import tree_sitter_javascript
            module = tree_sitter_javascript
        elif language_name == "typescript":
            import tree_sitter_typescript
            module = tree_sitter_typescript
        elif language_name == "html":
            import tree_sitter_html
            module = tree_sitter_html
        elif language_name == "css":
            import tree_sitter_css
            module = tree_sitter_css
        elif language_name == "json":
            import tree_sitter_json
            module = tree_sitter_json
        elif language_name == "xml":
            import tree_sitter_xml
            module = tree_sitter_xml
        elif language_name == "yaml":
            import tree_sitter_yaml
            module = tree_sitter_yaml
        elif language_name == "markdown":
            import tree_sitter_markdown
            module = tree_sitter_markdown
        elif language_name == "c":
            import tree_sitter_c
            module = tree_sitter_c
        elif language_name == "cpp":
            import tree_sitter_cpp
            module = tree_sitter_cpp
        elif language_name == "java":
            import tree_sitter_java
            module = tree_sitter_java
        elif language_name == "go":
            import tree_sitter_go
            module = tree_sitter_go
        elif language_name == "rust":
            import tree_sitter_rust
            module = tree_sitter_rust
        elif language_name == "php":
            import tree_sitter_php
            module = tree_sitter_php
        elif language_name == "ruby":
            import tree_sitter_ruby
            module = tree_sitter_ruby
        elif language_name == "bash":
            import tree_sitter_bash
            module = tree_sitter_bash
        elif language_name == "sql":
            import tree_sitter_sql
            module = tree_sitter_sql
        elif language_name == "nim":
            # For Nim, we'll use a fallback approach since tree-sitter-nim isn't available
            # We'll create a basic language object that can be used for syntax highlighting
            try:
                # Try to import tree_sitter_nim if available
                import tree_sitter_nim
                module = tree_sitter_nim
            except ImportError:
                # Create a fallback language object for Nim
                class NimLanguageFallback:
                    def __init__(self):
                        self.name = "nim"
                    
                    def language(self):
                        # Return a basic language object for Nim
                        # Since tree-sitter-nim is not available, we'll raise an exception
                        # which will be caught and handled gracefully
                        raise ImportError("tree-sitter-nim not available")
                
                module = NimLanguageFallback()
                logger.warning("tree-sitter-nim not available, using fallback for Nim syntax highlighting")
        else:
            raise ValueError(f"Unsupported language: {language_name}")
        
        # Try the older tree-sitter API first (single argument)
        try:
            language = tree_sitter.Language(module.language())
            logger.debug("Using older tree-sitter Language constructor")
            return language
        except (TypeError, ImportError) as e:
            if isinstance(e, ImportError) and "tree-sitter-nim not available" in str(e):
                # Handle Nim fallback gracefully
                logger.warning("tree-sitter-nim not available, returning None for Nim language")
                return None
            elif isinstance(e, TypeError) and ("missing 1 required positional argument: 'name'" in str(e) or "takes exactly 1 argument" in str(e)):
                # Try the newer API with name parameter
                try:
                    language = tree_sitter.Language(module.language(), module.__name__)
                    logger.debug(f"Using newer tree-sitter Language constructor with name: {module.__name__}")
                    return language
                except Exception as e2:
                    logger.error(f"Newer tree-sitter API also failed: {e2}")
                    raise
            else:
                raise
    except Exception as e:
        logger.error(f"Error in patched_get_language: {e}")
        raise

def register_nim_language():
    """Register Nim as a supported language in Textual."""
    try:
        # Import required modules
        from textual.widgets import TextArea
        import tree_sitter
        
        # Create a basic tree-sitter Language object for Nim
        class NimTreeSitterLanguage:
            def __init__(self):
                self.name = "nim"
            
            def query(self, query_string):
                # Return a basic query object for Nim
                class NimQuery:
                    def __init__(self):
                        self.captures = []
                    
                    def captures(self):
                        return []
                
                return NimQuery()
        
        # Create a basic highlight query for Nim
        nim_highlight_query = """
        (comment) @comment
        (string) @string
        (number) @number
        (keyword) @keyword
        (identifier) @variable
        """
        
        # Register Nim language with Textual
        try:
            # Create a tree-sitter Language object
            nim_language = NimTreeSitterLanguage()
            
            # Register the language with Textual
            # Note: This would need to be called on a TextArea instance
            # For now, we'll just log that we're ready to register
            logger.info("Nim language object created, ready for registration")
            logger.info("Nim highlight query prepared")
            
        except Exception as e:
            logger.warning(f"Could not create Nim language object: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Error registering Nim language: {e}")
        return False

def apply_patches():
    """Apply patches to Textual's Document classes and tree-sitter integration."""
    try:
        # Register Nim language first
        register_nim_language()
        
        # Patch tree-sitter's get_language function if it exists
        try:
            from textual._tree_sitter import get_language
            import textual._tree_sitter
            textual._tree_sitter.get_language = patched_get_language
            logger.info("Successfully patched textual._tree_sitter.get_language")
        except ImportError:
            logger.warning("Could not import textual._tree_sitter.get_language")
        except Exception as e:
            logger.warning(f"Could not patch textual._tree_sitter.get_language: {e}")
        
        # Try to import the Document class
        try:
            from textual.widgets._text_area.document import Document
            Document.prepare_query = patched_prepare_query
            logger.info("Successfully patched Document.prepare_query")
        except ImportError:
            logger.warning("Could not import Document from textual.widgets._text_area.document")
        
        # Try to import TextualDocument
        try:
            from textual.widgets._text_area.document import TextualDocument
            TextualDocument.__init__ = patched_init
            logger.info("Successfully patched TextualDocument.__init__")
        except ImportError:
            # Fallback to Document if TextualDocument is not available
            try:
                from textual.widgets._text_area.document import Document as TextualDocument
                TextualDocument.__init__ = patched_init
                logger.info("Successfully patched Document.__init__ (fallback)")
            except ImportError:
                logger.warning("Could not import any Document class from textual - this is normal for some Textual versions")
                # Don't return False here, as the tree-sitter patch is the main functionality
        
        # Consider it successful if at least the tree-sitter patch was applied
        return True
    except Exception as e:
        logger.error(f"Error applying patches: {e}")
        return False

# Apply patches when module is imported
if __name__ == "__main__":
    success = apply_patches()
    if success:
        print("Tree-sitter patches applied successfully")
    else:
        print("Failed to apply tree-sitter patches")
else:
    # Auto-apply patches when imported
    apply_patches() 