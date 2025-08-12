#!/usr/bin/env python3
"""Custom syntax-aware text editor widget for K2Edit."""

import asyncio
from pathlib import Path
from typing import Optional, Union, Callable, List, Dict, Any

from textual.widgets import TextArea
from textual.events import MouseDown, Key
from textual.geometry import Offset
from textual.containers import Container
from textual.widgets import ListView, ListItem, Static

# Import the Nim highlight module
from .nim_highlight import register_nim_language, is_nim_available
from .utils.language_utils import detect_language_by_extension

class CustomSyntaxEditor(TextArea):
    """Custom syntax-aware text editor with enhanced file handling."""
    
    def __init__(self, logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.current_file = None
        self.is_modified = False
        self.read_only = False
        

        self.show_line_numbers = True
        self.theme = "monokai"
        
        # Go-to-definition support
        self._goto_definition_callback = None
        self._lsp_client = None
        
        # Cursor position callback
        self.cursor_position_changed = None
        
        # Autocomplete support
        self._suggestion_popup = None
        self._suggestions = []
        self._selected_suggestion_index = 0
        self._autocomplete_enabled = True
        
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
        language = detect_language_by_extension(path.suffix.lower())
        await self._set_content_with_language("", language)
        
        await self.logger.info(f"CUSTOM EDITOR: Created new file buffer for: {path}")
        return True

    async def _load_existing_file(self, path: Path) -> bool:
        """Load content from an existing file."""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Set language based on file extension
        extension = path.suffix.lower()
        language = detect_language_by_extension(extension)
        
        await self._set_content_with_language(content, language)
        
        self.current_file = path
        self.is_modified = False
        self.read_only = False
        
        return True

    async def _set_content_with_language(self, content: str, language: Optional[str]) -> None:
        """Set content with language support."""
        self.text = content
        self.language = language if language and language != "unknown" else None

    async def load_file(self, file_path: Union[str, Path]) -> bool:
        """Load a file into the editor."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                return await self._create_new_file(path)
            else:
                return await self._load_existing_file(path)
            
        except Exception as e:
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

    def _get_language_from_file(self, file_path: str) -> str:
        """Determine the programming language from file extension."""
        if not file_path:
            return "text"
        
        extension = Path(file_path).suffix.lower()
        language = detect_language_by_extension(extension)
        return language if language != "unknown" else "text"

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
                line, char = self.get_character_at_coordinate(adjusted_x, adjusted_y)
                return line, char
            
            # Fallback: estimate based on visible lines and average character width
            lines = self.text.splitlines()
            line = max(0, min(adjusted_y, len(lines) - 1))
            
            # Estimate character position based on x coordinate and font width
            estimated_char = max(0, adjusted_x // 8)  # Assume 8px per character
            estimated_char = min(estimated_char, len(lines[line]) if line < len(lines) else 0)
            
            return line, estimated_char
            
        except (IndexError, ValueError) as e:
            self.logger.warning(f"CUSTOM EDITOR: Error converting mouse to text position: {e}")
            return 0, 0
        except Exception as e:
            self.logger.error(f"CUSTOM EDITOR: Unexpected error in mouse position conversion: {e}")
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
                
                await self.logger.info(f"Navigating to definition: {target_file}:{target_line}:{target_char}")
                
                # Trigger navigation
                self._goto_definition_callback(target_file, target_line, target_char)
            else:
                await self.logger.debug("No definitions found")
                    
        except (KeyError, ValueError, IndexError) as e:
            await self.logger.warning(f"Invalid definition format: {e}")
        except Exception as e:
            await self.logger.error(f"Unexpected error in go-to-definition: {e}")

    async def on_text_area_selection_changed(self, event) -> None:
        """Called when cursor position or selection changes."""
        line, column = self.cursor_location
        self.logger.debug(f"Cursor position changed: line {line}, column {column}")
        
        # Call the callback if it exists
        if hasattr(self, 'cursor_position_changed') and self.cursor_position_changed:
            self.cursor_position_changed(line, column)

    async def on_key(self, event: Key) -> None:
        """Handle key events for autocomplete functionality."""
        # Always check if popup is visible and handle navigation keys
        if self._suggestion_popup and self._suggestion_popup.display:
            handled = True
            if event.key == "escape":
                self._hide_suggestions()
            elif event.key == "up":
                self._select_previous_suggestion()
            elif event.key == "down":
                self._select_next_suggestion()
            elif event.key == "tab":
                if self._suggestions:
                    selected = self._suggestions[self._selected_suggestion_index]
                    await self._insert_completion(selected)
                    self._hide_suggestions()
                else:
                    self._hide_suggestions()
                    handled = False  # Allow default tab behavior
            elif event.key == "enter":
                if self._suggestions:
                    selected = self._suggestions[self._selected_suggestion_index]
                    await self._insert_completion(selected)
                    self._hide_suggestions()
                else:
                    handled = False  # Allow default enter behavior
            else:
                handled = False  # Let other keys pass through
            
            if handled:
                event.prevent_default()
                event.stop()
                return
        
        # Handle tab when no popup is visible
        if event.key == "tab" and (not self._suggestion_popup or not self._suggestion_popup.display):
            # Default tab behavior - insert 4 spaces
            self.insert_completion("    ")
            event.prevent_default()
            event.stop()
            return
        
        # Handle Ctrl+Shift+Space for manual autocomplete trigger
        if event.key == "ctrl+shift+space" and self._autocomplete_enabled and self._lsp_client and self.current_file:
            event.prevent_default()
            event.stop()
            await self._show_suggestions()
            return
        
        # Handle character typing for triggering autocomplete
        if event.is_printable and self._autocomplete_enabled and self._lsp_client and self.current_file:
            # Small delay to allow text to be inserted before querying
            asyncio.create_task(self._delayed_autocomplete_trigger())
        
        # Handle backspace and other editing keys
        if event.key in ["backspace", "delete"]:
            self._hide_suggestions()

    async def _delayed_autocomplete_trigger(self, delay: float = 0.15):
        """Trigger autocomplete after a short delay to allow text insertion."""
        await asyncio.sleep(delay)
        
        # Check if we should trigger autocomplete
        if not self._should_trigger_autocomplete():
            return
            
        await self._show_suggestions()

    def _should_trigger_autocomplete(self) -> bool:
        """Determine if autocomplete should be triggered based on context."""
        line, column = self.cursor_location
        lines = self.text.splitlines()
        
        if line >= len(lines):
            return False
            
        current_line = lines[line] if line < len(lines) else ""
        
        # Don't trigger on empty lines or at start of line
        if column <= 0:
            return False
            
        # Get text before cursor
        text_before_cursor = current_line[:column]
        
        # Simple trigger: any non-whitespace character
        if column > 0 and not text_before_cursor[-1].isspace():
            return True
            
        return False

    async def _show_suggestions(self):
        """Show autocomplete suggestions from LSP server."""
        if not self._lsp_client or not self.current_file:
            self.logger.debug("LSP client or current file not available")
            return
        
        self.logger.debug(f"AUTOCOMPLETE: Attempting to show suggestions for {self.current_file}")
        
        try:
            language = self._get_language_from_file(str(self.current_file))
            if not language or language == "text":
                self.logger.debug(f"No language detected for file: {self.current_file}")
                return
            
            if not self._lsp_client.is_server_running(language):
                self.logger.debug(f"LSP server not running for language: {language}")
                return
            
            line, character = self.cursor_location
            
            self.logger.debug(f"Requesting completions for {self.current_file}:{line}:{character}")
            
            # Get completions from LSP
            completions = await self._lsp_client.get_completions(
                str(self.current_file),
                line,
                character,
                language
            )
            
            if completions and len(completions) > 0:
                self.logger.debug(f"Found {len(completions)} completions")
                self._suggestions = completions
                self._selected_suggestion_index = 0
                await self._render_suggestions()
            else:
                self.logger.debug("No completions found")
                self._hide_suggestions()
                
        except (KeyError, ValueError) as e:
            await self.logger.error(f"Invalid LSP response format: {e}")
            self._hide_suggestions()
        except Exception as e:
            await self.logger.error(f"Unexpected error showing suggestions: {e}")
            self._hide_suggestions()

    async def _render_suggestions(self):
        """Render the suggestion popup with current suggestions."""
        if not self._suggestions:
            return
        
        # Create suggestion popup if it doesn't exist
        if not self._suggestion_popup:
            self._suggestion_popup = Container(
                ListView(
                    id="suggestion_list"
                ),
                id="suggestion_popup",
                classes="suggestion-popup"
            )
            self.mount(self._suggestion_popup)
        
        # Update suggestion list
        suggestion_list = self._suggestion_popup.query_one("#suggestion_list", ListView)
        suggestion_list.clear()
        
        for i, suggestion in enumerate(self._suggestions[:10]):  # Limit to 10 suggestions
            label = suggestion.get("label", "")
            detail = suggestion.get("detail", "")
            kind = suggestion.get("kind", 0)
            
            # Create display text with better formatting
            display_text = label  # Use label as primary display
            
            # Add type indicator
            type_indicator = ""
            if kind:
                kind_map = {
                    1: "📄", 2: "🔧", 3: "⚙️", 4: "🏗️", 5: "📋", 6: "📊", 7: "📦",
                    8: "🔗", 9: "📚", 10: "🔑", 14: "🔍", 15: "📋", 21: "🔢"
                }
                type_indicator = kind_map.get(kind, "")
            
            display_text = f"{type_indicator} {label}"
            if detail and detail != label and len(detail) < 30:
                display_text += f" - {detail}"
            
            item = ListItem(Static(display_text), classes="suggestion-item")
            if i == self._selected_suggestion_index:
                item.add_class("selected")
            
            suggestion_list.append(item)
        
        # Position popup near cursor
        line, column = self.cursor_location
        self._position_popup(line, column)
        
        self._suggestion_popup.display = True

    def _position_popup(self, line: int, column: int):
        """Position the suggestion popup near the cursor."""
        if not self._suggestion_popup:
            return
        
        # Position popup below the cursor line
        # Use relative positioning within the editor
        char_width = 1  # Approximate character width
        line_height = 1  # Line height
        
        popup_x = max(0, column * char_width)
        popup_y = max(0, (line + 1) * line_height)
        
        # Set reasonable dimensions
        self._suggestion_popup.styles.width = 30
        self._suggestion_popup.styles.height = min(len(self._suggestions), 8)
        self._suggestion_popup.styles.offset = (popup_x, popup_y)
        self._suggestion_popup.styles.layer = "popup"

    def _select_next_suggestion(self):
        """Select the next suggestion in the list."""
        if self._suggestions:
            self._selected_suggestion_index = (self._selected_suggestion_index + 1) % len(self._suggestions)
            asyncio.create_task(self._render_suggestions())

    def _select_previous_suggestion(self):
        """Select the previous suggestion in the list."""
        if self._suggestions:
            self._selected_suggestion_index = (self._selected_suggestion_index - 1) % len(self._suggestions)
            asyncio.create_task(self._render_suggestions())

    def _hide_suggestions(self):
        """Hide the suggestion popup."""
        if self._suggestion_popup:
            self._suggestion_popup.display = False
        self._suggestions = []
        self._selected_suggestion_index = 0

    async def _insert_completion(self, suggestion: Dict[str, Any]):
        """Insert the selected completion into the editor."""
        try:
            insert_text = suggestion.get("insertText", "")
            if not insert_text:
                insert_text = suggestion.get("label", "")
            
            # Handle textEdit if provided
            text_edit = suggestion.get("textEdit")
            if text_edit:
                new_text = text_edit.get("newText", "")
                range_info = text_edit.get("range", {})
                start = range_info.get("start", {})
                end = range_info.get("end", {})
                
                # For simplicity, just use newText
                insert_text = new_text
            
            if insert_text:
                self.insert_completion(insert_text)
                
        except Exception as e:
            await self.logger.error(f"Error inserting completion: {e}")

    def insert_completion(self, text: str):
        """Insert completion text at cursor position."""
        try:
            # Get current cursor position
            line, column = self.cursor_location
            
            # Get current text lines
            lines = self.text.splitlines(True)
            if line >= len(lines):
                lines.append(text)
            else:
                current_line = lines[line]
                new_line = current_line[:column] + text + current_line[column:]
                lines[line] = new_line
            
            # Update text
            self.text = "".join(lines)
            
            # Move cursor to end of inserted text
            new_column = column + len(text)
            self.cursor_location = (line, new_column)
            
        except Exception as e:
            self.logger.error(f"Error inserting completion: {e}")

    def toggle_autocomplete(self, enabled: bool = None):
        """Toggle autocomplete functionality on/off."""
        if enabled is None:
            self._autocomplete_enabled = not self._autocomplete_enabled
        else:
            self._autocomplete_enabled = enabled
        
        if not self._autocomplete_enabled:
            self._hide_suggestions()
        
        self.logger.info(f"Autocomplete {'enabled' if self._autocomplete_enabled else 'disabled'}")