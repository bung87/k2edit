#!/usr/bin/env python3
"""Custom syntax-aware text editor widget for K2Edit."""

import asyncio
from pathlib import Path
from typing import Optional, Union, Callable, List, Dict, Any

from textual.widgets import TextArea
from textual.events import MouseDown
from textual.geometry import Offset

# Import the Nim highlight module
from .nim_highlight import register_nim_language, is_nim_available

class CustomSyntaxEditor(TextArea):
    """Custom syntax-aware text editor with enhanced file handling."""
    
    def __init__(self, logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
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
        
        # Go-to-definition support
        self._goto_definition_callback = None
        self._lsp_client = None
        
        # Cursor position callback
        self.cursor_position_changed = None
        
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

    async def _create_new_file(self, path: Path) -> bool:
        """Create a new file buffer."""
        self.current_file = path
        self.is_modified = False
        self.read_only = False
        
        # Try to set language and load content with fallback to plain text if parsing fails
        language = self._language_map.get(path.suffix.lower(), "text")
        await self._set_content_with_language("", language)
        
        if self.logger:
             await self.logger.info(f"CUSTOM EDITOR: Created new file buffer for: {path}")
        return True

    async def _load_existing_file(self, path: Path) -> bool:
        """Load content from an existing file."""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Set language based on file extension
        extension = path.suffix.lower()
        language = self._language_map.get(extension)
        
        await self._set_content_with_language(content, language)
        
        self.current_file = path
        self.is_modified = False
        self.read_only = False
        
        return True

    async def _set_content_with_language(self, content: str, language: Optional[str]) -> None:
        """Set content with language support, falling back to plain text if needed."""
        try:
            # Use built-in tree-sitter support from Textual
            if language and language != "text":
                try:
                    # Set the text and language properties
                    self.text = content
                    self.language = language
                except Exception as e:
                    # Language not supported or other error, fall back to plain text
                    await self.logger.debug(f"CUSTOM EDITOR: Language '{language}' not available: {e}")
                    self.text = content
                    self.language = None
            else:
                self.text = content
                self.language = None
        except ValueError as e:
            if "Parsing failed" in str(e):
                if self.logger:
                     await self.logger.warning(f"CUSTOM_EDITOR: Tree-sitter parsing failed, falling back to plain text mode")
                self.text = content
                self.language = None  # Fall back to plain text
            else:
                raise  # Re-raise if it's a different ValueError

    async def load_file(self, file_path: Union[str, Path]) -> bool:
        """Load a file into the editor."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                return await self._create_new_file(path)
            else:
                return await self._load_existing_file(path)
            
        except Exception as e:
            if self.logger:
                 await self.logger.error(f"CUSTOM EDITOR: Error loading file {file_path}: {e}", exc_info=True)
            return False

    def get_selected_text(self) -> Optional[str]:
        """Get the currently selected text. Returns None if no selection."""
        return self.selected_text

    def set_lsp_client(self, lsp_client):
        """Set the LSP client for go-to-definition functionality."""
        self._lsp_client = lsp_client

    def set_goto_definition_callback(self, callback: Callable[[List[Dict[str, Any]]], None]):
        """Set the callback for handling go-to-definition navigation."""
        self._goto_definition_callback = callback

    def _get_language_from_file(self, file_path: str) -> Optional[str]:
        """Determine the programming language from file extension."""
        if not file_path:
            return None
        
        extension = Path(file_path).suffix.lower()
        return self._language_map.get(extension)

    def _get_text_position_from_mouse(self, offset: Offset) -> tuple[int, int]:
        """Convert mouse position to text position (line, character)."""
        # Get the text position from mouse coordinates
        # This is a simplified implementation - may need adjustment based on Textual's actual API
        try:
            # TextArea has get_offset_to_location method
            location = self.get_offset_to_location(offset)
            return location.line, location.column
        except Exception:
            # Fallback to cursor position if conversion fails
            return self.cursor_location

    def on_mouse_down(self, event: MouseDown) -> None:
        """Handle mouse down events for Ctrl+Click go-to-definition."""
        super().on_mouse_down(event)
        
        # Check if Ctrl key is pressed
        if not (event.ctrl or event.control):
            return
            
        # Get current file path
        if not self.current_file:
            return
            
        # Convert mouse position to text position
        line, character = self._get_text_position_from_mouse(event.offset)
        
        # Check if LSP client is available
        if not self._lsp_client or not self._goto_definition_callback:
            return
            
        # Get language for current file
        language = self._get_language_from_file(str(self.current_file))
        if not language:
            return
            
        # Check if LSP server is running for this language
        if not self._lsp_client.is_server_running(language):
            return
            
        # Trigger async go-to-definition request
        asyncio.create_task(self._trigger_goto_definition(line, character))

    async def _trigger_goto_definition(self, line: int, character: int) -> None:
        """Send go-to-definition request to LSP server."""
        try:
            if not self._lsp_client or not self._goto_definition_callback:
                return
                
            # Get language for current file
            language = self._get_language_from_file(str(self.current_file))
            if not language or language == "unknown":
                return
                
            definitions = await self._lsp_client.get_definition(
                language,
                str(self.current_file),
                line,
                character
            )
            
            if definitions:
                await self._goto_definition_callback(definitions)
                
        except Exception as e:
            # Log error but don't crash the editor
            if hasattr(self, 'logger') and self.logger:
                await self.logger.error(f"Error in go-to-definition: {e}")
            else:
                print(f"Error in go-to-definition: {e}")

    async def save_file(self, file_path: Optional[Union[str, Path]] = None) -> bool:
        """Save the current content to a file."""
        try:
            path = Path(file_path) if file_path else self.current_file
            if not path:
                await self.logger.error("CUSTOM EDITOR: No file path specified for saving.")
                return False

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write content to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.text)

            self.current_file = path
            self.is_modified = False

            await self.logger.info(f"CUSTOM EDITOR: Successfully saved file: {path}")
            
            return True

        except Exception as e:
            await self.logger.error(f"CUSTOM EDITOR: Error saving file: {e}", exc_info=True)
            return False

    @property
    def cursor_line(self) -> int:
        """Get cursor line."""
        return self.cursor_location[0]

    @property
    def cursor_column(self) -> int:
        """Get cursor column."""
        return self.cursor_location[1]

    def set_lsp_client(self, lsp_client):
        """Set the LSP client for go-to-definition functionality."""
        self._lsp_client = lsp_client
        
    def set_goto_definition_callback(self, callback: Callable[[str, int, int], None]):
        """Set callback for go-to-definition navigation."""
        self._goto_definition_callback = callback

    def _get_language_from_file(self, file_path: str) -> str:
        """Get language identifier from file path."""
        if not file_path:
            return "text"
        
        path = Path(file_path)
        extension = path.suffix.lower()
        return self._language_map.get(extension, "text")

    def _convert_mouse_to_text_position(self, x: int, y: int) -> tuple[int, int]:
        """Convert mouse coordinates to text position (line, character)."""
        try:
            # Get the visible region of the text area
            region = self.region
            
            # Account for line numbers and padding
            line_number_width = len(str(len(self.text.splitlines()))) + 2 if self.show_line_numbers else 0
            
            # Adjust x for line numbers
            adjusted_x = x - region.x - line_number_width
            adjusted_y = y - region.y
            
            # Get character position from coordinates
            if hasattr(self, 'get_character_at_coordinate'):
                # Try to use Textual's built-in method if available
                try:
                    line, char = self.get_character_at_coordinate(adjusted_x, adjusted_y)
                    return line, char
                except (IndexError, ValueError):
                    pass
            
            # Fallback: estimate based on visible lines and average character width
            lines = self.text.splitlines()
            line = max(0, min(adjusted_y, len(lines) - 1))
            
            # Estimate character position based on x coordinate and font width
            # This is a rough approximation - exact positioning depends on font metrics
            estimated_char = max(0, adjusted_x // 8)  # Assume 8px per character
            estimated_char = min(estimated_char, len(lines[line]) if line < len(lines) else 0)
            
            return line, estimated_char
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error converting mouse to text position: {e}")
            return 0, 0

    async def on_mouse_down(self, event: MouseDown) -> None:
        """Handle mouse down events for Ctrl+Click go-to-definition."""
        if not (event.ctrl and self._lsp_client and self.current_file):
            # Normal click handling - do nothing, let Textual handle it
            return
            
        try:
            # Convert mouse position to text position
            line, character = self._convert_mouse_to_text_position(event.x, event.y)
            
            # Get language for the current file
            language = self._get_language_from_file(str(self.current_file))
            
            # Check if LSP server is running for this language
            if not self._lsp_client.is_server_running(language):
                if self.logger:
                    await self.logger.debug(f"LSP server not running for language: {language}")
                return
                
            # Send go-to-definition request
            definitions = await self._lsp_client.get_definition(
                language, 
                str(self.current_file), 
                line, 
                character
            )
            
            if definitions and self._goto_definition_callback:
                # Navigate to the first definition
                definition = definitions[0]
                uri = definition.get("uri", "")
                range_info = definition.get("range", {})
                start = range_info.get("start", {})
                
                target_file = uri.replace("file://", "") if uri else str(self.current_file)
                target_line = start.get("line", line) + 1  # LSP uses 0-based lines
                target_char = start.get("character", 0) + 1  # LSP uses 0-based characters
                
                if self.logger:
                    await self.logger.debug(f"Navigating to definition: {target_file}:{target_line}:{target_char}")
                
                # Trigger navigation
                self._goto_definition_callback(target_file, target_line, target_char)
            else:
                if self.logger:
                    await self.logger.debug("No definition found for symbol")
                    
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error in go-to-definition: {e}")

    async def on_text_area_selection_changed(self, event) -> None:
        """Called when cursor position or selection changes."""
        line, column = self.cursor_location
        await self.logger.debug(f"CUSTOM EDITOR: Cursor moved to line {line}, column {column}")
        await self.logger.debug(f"CUSTOM EDITOR: Raw cursor_location: {self.cursor_location}")
        await self.logger.debug(f"CUSTOM EDITOR: Event details: {event}")

        # Call the callback if it exists
        if hasattr(self, 'cursor_position_changed') and self.cursor_position_changed:
            await self.logger.debug(f"CUSTOM EDITOR: Calling cursor_position_changed with ({line}, {column})")
            self.cursor_position_changed(line, column)