from pathlib import Path
from typing import Union, Optional

from textual.widgets import TextArea
from tree_sitter_languages import get_language
import logging

class CustomSyntaxEditor(TextArea):
    """A custom editor widget based on Textual's TextArea."""

    def __init__(self, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self._app_instance = app_instance
        self.current_file: Optional[Path] = None
        self.is_modified = False

        # Language mapping for syntax highlighting
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
        self._show_welcome_screen()

    def _show_welcome_screen(self):
        """Display a welcome screen when no file is loaded."""
        welcome_text = """

  ╭─────────────────────────────────────────────╮
  │                                             │
  │         K2Edit - Code Editor                │
  │                                             │
  │  Press Ctrl+O to open a file                │
  │  Use file explorer (left) to browse         │
  │  Press Ctrl+K for command bar             │
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
                self.load_text("")
                self.current_file = path
                self.is_modified = False
                self.read_only = False
                self.language = self._language_map.get(path.suffix.lower(), "text")
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.info(f"CUSTOM EDITOR: Created new file buffer for: {path}")
                return True
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Set language based on file extension
            extension = path.suffix.lower()
            language = self._language_map.get(extension)

            try:
                self.language = get_language(language)
            except Exception as e:
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.error(f"CUSTOM EDITOR: Failed to load language '{language}': {e}")
                self.language = None
            self.load_text(content)
            self.current_file = path
            self.is_modified = False
            self.read_only = False
            
            if language:
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.info(f"CUSTOM EDITOR: Using syntax highlighting for language: {language}")
            else:
                self.language = None # Default to plain text
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.info("CUSTOM EDITOR: No language mapping found, using plain text highlighting")
            
            if self._app_instance and hasattr(self._app_instance, 'logger'):
                self._app_instance.logger.info(f"CUSTOM EDITOR: Successfully loaded file: {path}")
            
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