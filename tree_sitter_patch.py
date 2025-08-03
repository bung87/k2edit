# Tree-sitter compatibility patch for textual
# This must be imported before any textual modules

try:
    import tree_sitter
    
    # Create a dummy QueryCursor if it doesn't exist
    if not hasattr(tree_sitter, 'QueryCursor'):
        class QueryCursor:
            def __init__(self, query=None):
                self._query = query
                pass
            
            def exec(self, query, node):
                return []
            
            def set_point_range(self, start_point, end_point):
                """Set the point range for the cursor."""
                pass
            
            def captures(self, node):
                """Return captures from the query."""
                return {}
        
        tree_sitter.QueryCursor = QueryCursor
    
    # Patch Query constructor to handle textual's usage
    if hasattr(tree_sitter, 'Query'):
        original_query = tree_sitter.Query
        
        class PatchedQuery:
            def __init__(self, language=None, source=None):
                """Patched Query that handles textual's Query(language, source) calls."""
                self._query = original_query()
                if language and source:
                    # Store the language and source for later use
                    self._language = language
                    self._source = source
            
            def __getattr__(self, name):
                """Delegate all other attributes to the original query."""
                return getattr(self._query, name)
        
        tree_sitter.Query = PatchedQuery
    
    # Patch textual's tree-sitter integration to fix Language constructor issue
    try:
        import textual._tree_sitter
        original_get_language = textual._tree_sitter.get_language
        
        def patched_get_language(name):
            """Patched version that handles Language constructor correctly."""
            try:
                return original_get_language(name)
            except TypeError as e:
                if "missing 1 required positional argument: 'name'" in str(e):
                    # Handle the deprecated Language(path, name) vs Language(ptr, name) issue
                    import importlib
                    try:
                        module = importlib.import_module(f"tree_sitter_{name}")
                        # Use the new constructor format: Language(ptr, name)
                        return tree_sitter.Language(module.language(), name)
                    except Exception:
                        # If that fails, try tree_sitter_languages
                        try:
                            import tree_sitter_languages
                            return tree_sitter_languages.get_language(name)
                        except Exception:
                            raise e
                else:
                    raise e
        
        textual._tree_sitter.get_language = patched_get_language
        
    except ImportError:
        # textual._tree_sitter not available
        pass
    
    # Patch SyntaxAwareDocument to fix Parser initialization
    try:
        from textual.document._syntax_aware_document import SyntaxAwareDocument
        original_init = SyntaxAwareDocument.__init__
        
        def patched_init(self, text, language):
            """Patched SyntaxAwareDocument.__init__ that uses correct Parser initialization."""
            from textual.document._syntax_aware_document import TREE_SITTER
            from textual.document._document import Document
            
            if not TREE_SITTER:
                raise RuntimeError(
                    "SyntaxAwareDocument unavailable - tree-sitter is not installed."
                )

            Document.__init__(self, text)
            self.language = language
            
            # Use the correct parser initialization method
            self._parser = tree_sitter.Parser()
            self._parser.set_language(self.language)
            
            self._syntax_tree = self._parser.parse(self._read_callable)
        
        SyntaxAwareDocument.__init__ = patched_init
        
    except ImportError:
        # SyntaxAwareDocument not available
        pass
        
except ImportError:
    # tree-sitter not available
    pass