#!/usr/bin/env python3
"""Custom syntax-aware text editor widget for K2Edit."""

from pathlib import Path
from typing import Optional, Union

from textual.widgets import TextArea

# Import the Nim highlight module
from .nim_highlight import register_nim_language, is_nim_available

class CustomSyntaxEditor(TextArea):
    """Custom syntax-aware text editor with enhanced file handling."""
    
    def __init__(self, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self._app_instance = app_instance
        self.current_file = None
        self.is_modified = False
        self.read_only = False
        
        # Language mapping for file extensions
        self._language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.nim': 'nim',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.sh': 'bash',
            '.sql': 'sql',
        }
        self.show_line_numbers = True
        self.theme = "monokai"
        
        # Register Nim language with Textual
        self._register_nim_language()

    def _register_nim_language(self):
        """Register Nim as a supported language in Textual."""
        if is_nim_available():
            success = register_nim_language(self)
            # Note: Logging removed to avoid async logger issues during __init__
            # The registration will be logged later when the app is running
        else:
            # Note: Logging removed to avoid async logger issues during __init__
            pass

    def _show_welcome_screen(self):
        """Display a welcome screen when no file is loaded."""
        welcome_text = """

  ╭─────────────────────────────────────────────╮
  │                                             │
  │         K2Edit - Code Editor                │
  │                                             │
  │  Press Ctrl+O to open a file                │
  │  Use file explorer (left) to browse         │
  │  Press Ctrl+K for command bar               │
  │                                             │
  ╰─────────────────────────────────────────────╯

  Ready to edit! Select a file to begin.
"""
        self.load_text(welcome_text)
        self.language = None
        self.read_only = True

    def load_file(self, file_path: Union[str, Path]) -> bool:
        """Load a file into the editor."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                # Create new file
                self.current_file = path
                self.is_modified = False
                self.read_only = False
                
                # Try to set language and load content with fallback to plain text if parsing fails
                language = self._language_map.get(path.suffix.lower(), "text")
                try:
                    # Use built-in tree-sitter support from Textual
                    if language and language != "text":
                        try:
                            # Set the text and language properties
                            self.text = ""
                            self.language = language
                        except Exception as e:
                            # Language not supported or other error, fall back to plain text
                            if self._app_instance and hasattr(self._app_instance, 'logger'):
                                self._app_instance.logger.debug(f"CUSTOM EDITOR: Language '{language}' not available: {e}")
                            self.text = ""
                            self.language = None
                    else:
                        self.text = ""
                        self.language = None
                except ValueError as e:
                    if "Parsing failed" in str(e):
                        if self._app_instance and hasattr(self._app_instance, 'logger'):
                            self._app_instance.logger.warning(f"CUSTOM EDITOR: Tree-sitter parsing failed for new file {path}, falling back to plain text mode")
                        self.text = ""
                        self.language = None  # Fall back to plain text
                    else:
                        raise  # Re-raise if it's a different ValueError
                
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.info(f"CUSTOM EDITOR: Created new file buffer for: {path}")
                return True
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Set language based on file extension
            extension = path.suffix.lower()
            language = self._language_map.get(extension)
            
            # Try to load content with syntax highlighting, fall back to plain text if parsing fails
            try:
                # Use built-in tree-sitter support from Textual
                if language and language != "text":
                    try:
                        # Set the text and language properties
                        self.text = content
                        self.language = language
                    except Exception as e:
                        # Language not supported or other error, fall back to plain text
                        if self._app_instance and hasattr(self._app_instance, 'logger'):
                            self._app_instance.logger.debug(f"CUSTOM EDITOR: Language '{language}' not available: {e}")
                        self.text = content
                        self.language = None
                else:
                    self.text = content
                    self.language = None
            except ValueError as e:
                if "Parsing failed" in str(e):
                    if self._app_instance and hasattr(self._app_instance, 'logger'):
                        self._app_instance.logger.warning(f"CUSTOM_EDITOR: Tree-sitter parsing failed for {path}, falling back to plain text mode")
                    self.text = content
                    self.language = None  # Fall back to plain text
                else:
                    raise  # Re-raise if it's a different ValueError
            
            self.current_file = path
            self.is_modified = False
            self.read_only = False
            
            return True
            
        except Exception as e:
            if self._app_instance and hasattr(self._app_instance, 'logger'):
                self._app_instance.logger.error(f"CUSTOM EDITOR: Error loading file {file_path}: {e}", exc_info=True)
            return False

    def get_selected_text(self) -> Optional[str]:
        """Get the currently selected text. Returns None if no selection."""
        return self.selected_text

    def save_file(self, file_path: Optional[Union[str, Path]] = None) -> bool:
        """Save the current content to a file."""
        try:
            path = Path(file_path) if file_path else self.current_file
            if not path:
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.error("CUSTOM EDITOR: No file path specified for saving.")
                return False

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write content to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.text)

            self.current_file = path
            self.is_modified = False

            if self._app_instance and hasattr(self._app_instance, 'logger'):
                self._app_instance.logger.info(f"CUSTOM EDITOR: Successfully saved file: {path}")
            
            return True

        except Exception as e:
            if self._app_instance and hasattr(self._app_instance, 'logger'):
                self._app_instance.logger.error(f"CUSTOM EDITOR: Error saving file: {e}", exc_info=True)
            return False

    @property
    def cursor_line(self) -> int:
        """Get cursor line."""
        return self.cursor_location[0]

    @property
    def cursor_column(self) -> int:
        """Get cursor column."""
        return self.cursor_location[1]

    def on_text_area_selection_changed(self, event) -> None:
        """Called when cursor position or selection changes."""
        line, column = self.cursor_location
        if self._app_instance and hasattr(self._app_instance, 'logger'):
            self._app_instance.logger.debug(f"CUSTOM EDITOR: Cursor moved to line {line}, column {column}")
        
        # Call the callback if it exists
        if hasattr(self, 'cursor_position_changed') and self.cursor_position_changed:
            self.cursor_position_changed(line, column)