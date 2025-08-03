from pathlib import Path
from typing import Union, Optional
from textual.scroll_view import ScrollView
from textual.reactive import reactive
from textual.strip import Strip
from textual.geometry import Region, Size, Offset
from textual.events import Key, Click
from textual.coordinate import Coordinate
from rich.console import Console
from rich.syntax import Syntax
from rich.segment import Segment
from rich.text import Text
from rich.style import Style
import logging

class CustomSyntaxEditor(ScrollView, can_focus=True):
    """A custom editor widget with Rich syntax highlighting, line numbers, and cursor."""
    
    # Reactive properties for cursor and content - disable layout triggers
    text = reactive("")
    cursor_line = reactive(0)
    cursor_column = reactive(0)
    # scroll_offset is now handled by Textual's scrolling system
    show_line_numbers = reactive(True, layout=False)
    
    def watch_text(self, old_text: str, new_text: str) -> None:
        """Watch text changes and update content appropriately."""
        self.update_virtual_size()
        self.refresh(layout=True)
        
    def watch_cursor_line(self, old_line: int, new_line: int) -> None:
        """Watch cursor line changes and ensure cursor visibility."""
        pass
        
    def watch_cursor_column(self, old_column: int, new_column: int) -> None:
        """Watch cursor column changes and ensure cursor visibility."""
        pass
        
    def watch_show_line_numbers(self, old_value: bool, new_value: bool) -> None:
        """Watch line numbers visibility - refresh but don't affect layout width."""
        self.refresh()
    
    BINDINGS = [
        ("up", "cursor_up", "Move cursor up"),
        ("down", "cursor_down", "Move cursor down"),
        ("left", "cursor_left", "Move cursor left"),
        ("right", "cursor_right", "Move cursor right"),
        ("home", "cursor_home", "Move to start of line"),
        ("end", "cursor_end", "Move to end of line"),
        ("pageup", "page_up", "Page up"),
        ("pagedown", "page_down", "Page down"),
        ("ctrl+up", "scroll_up", "Scroll up"),
        ("ctrl+down", "scroll_down", "Scroll down"),
    ]
    
    def __init__(self, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self._app_instance = app_instance
        self._rich_console = Console(width=80, legacy_windows=False)
        self._syntax_language = None
        self.current_file = None
        self.is_modified = False
        self._line_number_width = 4
        
        # Enable scrollbars - these are set via CSS or widget properties
        self.can_focus = True
        
        # Set initial virtual size
        self.virtual_size = Size(100, 1)
        
        # Language mapping
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
    
    def _add_cursor_to_plain_text(self, line_text: str) -> list[Segment]:
        """Add cursor to plain text line."""
        # Replace tabs with 4 spaces for consistent alignment, matching get_content_width
        display_line = line_text.replace('\t', '    ').replace('\r', '')
        
        before_cursor = display_line[:self.cursor_column]
        cursor_char = display_line[self.cursor_column:self.cursor_column + 1] if self.cursor_column < len(display_line) else " "
        after_cursor = display_line[self.cursor_column + 1:] if self.cursor_column < len(display_line) else ""
        
        segments = []
        if before_cursor:
            segments.append(Segment(before_cursor))
        segments.append(Segment(cursor_char, Style.parse("black on white")))
        if after_cursor:
            segments.append(Segment(after_cursor))
        
        return segments
    
    def _add_cursor_to_segments(self, line_segments: list[Segment], line_text: str) -> list[Segment]:
        """Add cursor to syntax-highlighted line segments."""
        if not line_segments:
            return self._add_cursor_to_plain_text(line_text)
        
        # Find the position in segments where cursor should be
        cursor_segments = []
        current_pos = 0
        cursor_added = False
        
        for segment in line_segments:
            segment_text = segment.text
            segment_end = current_pos + len(segment_text)
            
            if not cursor_added and current_pos <= self.cursor_column < segment_end:
                # Cursor is within this segment
                offset = self.cursor_column - current_pos
                before = segment_text[:offset]
                cursor_char = segment_text[offset:offset + 1] if offset < len(segment_text) else " "
                after = segment_text[offset + 1:] if offset < len(segment_text) else ""
                
                if before:
                    cursor_segments.append(Segment(before, segment.style))
                cursor_segments.append(Segment(cursor_char, Style.parse("black on white")))
                if after:
                    cursor_segments.append(Segment(after, segment.style))
                cursor_added = True
            elif not cursor_added and self.cursor_column == current_pos:
                # Cursor is at the start of this segment
                cursor_segments.append(Segment(" ", Style.parse("black on white")))
                cursor_segments.append(segment)
                cursor_added = True
            else:
                cursor_segments.append(segment)
            
            current_pos = segment_end
        
        # If cursor is at the end of the line
        if not cursor_added and self.cursor_column >= len(line_text):
            cursor_segments.append(Segment(" ", Style.parse("black on white")))
        
        return cursor_segments
    
    def _truncate_segments_to_width(self, segments: list[Segment], max_width: int) -> list[Segment]:
        """Truncate segments to fit within the specified width."""
        if max_width <= 0:
            return []
        
        truncated_segments = []
        current_width = 0
        
        for segment in segments:
            segment_text = segment.text
            segment_length = len(segment_text)
            
            if current_width + segment_length <= max_width:
                # Entire segment fits
                truncated_segments.append(segment)
                current_width += segment_length
            elif current_width < max_width:
                # Partial segment fits
                remaining_width = max_width - current_width
                truncated_text = segment_text[:remaining_width]
                if truncated_text:
                    truncated_segments.append(Segment(truncated_text, segment.style))
                break
            else:
                # No more space
                break
        
        return truncated_segments
    
    def _apply_horizontal_scroll(self, segments: list[Segment], scroll_x: int) -> list[Segment]:
        """Apply horizontal scroll offset to segments."""
        if scroll_x <= 0:
            return segments
        
        scrolled_segments = []
        current_pos = 0
        
        for segment in segments:
            segment_text = segment.text
            segment_end = current_pos + len(segment_text)
            
            if segment_end <= scroll_x:
                # This segment is completely scrolled out
                current_pos = segment_end
                continue
            elif current_pos < scroll_x < segment_end:
                # This segment is partially scrolled out
                visible_start = scroll_x - current_pos
                visible_text = segment_text[visible_start:]
                if visible_text:
                    scrolled_segments.append(Segment(visible_text, segment.style))
            else:
                # This segment is completely visible
                scrolled_segments.append(segment)
            
            current_pos = segment_end
        
        return scrolled_segments
    

    

    
    def get_content_width(self) -> int:
        """Get the width of the content for horizontal scrolling."""
        if not self.text:
            return 0  # Return 0 if no text

        lines = self.text.split('\n')
        # Account for tab expansion (4 spaces per tab)
        expanded_lines = [line.replace('\t', '    ') for line in lines]
        max_line_length = max(len(line) for line in expanded_lines) if expanded_lines else 0
        
        # Return the actual max line length
        return max_line_length
    
    def get_content_height(self) -> int:
        """Get the height of the content for vertical scrolling."""
        if not self.text:
            return 1
        
        lines = self.text.split('\n')
        return len(lines)
    
    def update_virtual_size(self) -> None:
        """Update virtual size based on content, independent of container size."""
        # Calculate content dimensions
        content_width = self.get_content_width()
        content_height = self.get_content_height()
        
        # The virtual width should be based on the content, not the container.
        # This prevents the container from shrinking the virtual space.
        # A minimum height is set to ensure the editor doesn't collapse when empty.
        self.virtual_size = Size(content_width, max(content_height, 20))
        if self._app_instance and hasattr(self._app_instance, 'logger'):
            self._app_instance.logger.debug(f"Updated virtual size to: {self.virtual_size}")
    
    def render_line(self, y: int) -> Strip:
        """Render a single line with line numbers."""
        line_index = self.scroll_offset.y + y

        if not self.current_file and not self.text:
            return self._render_welcome_screen(y)

        scroll_x, _ = self.scroll_offset
        lines = self.text.split('\n')

        if line_index >= len(lines):
            return Strip.blank(self.size.width)

        line = lines[line_index]

        # --- Line Number Rendering ---
        line_number_segments = []
        line_number_width = 0
        if self.show_line_numbers:
            line_number_width = self._line_number_width + 3
            line_number_str = str(line_index + 1).rjust(self._line_number_width)
            line_number_segments.append(Segment(f"{line_number_str} │ ", Style(color="#6c7086")))

        # --- Content Rendering ---
        # Always expand tabs for consistent width calculation
        expanded_line = line.replace('\t', '    ')
        style = Style.parse("white on #272822") # Default style

        if self._syntax_language:
            try:
                syntax = Syntax(line, self._syntax_language, theme="monokai", line_numbers=False, word_wrap=False, tab_size=4)
                rendered_lines = list(self._rich_console.render_lines(syntax))
                if rendered_lines:
                    content_segments = rendered_lines[0]
                else:
                    content_segments = [Segment(expanded_line, style)] # Fallback
            except Exception:
                content_segments = [Segment(expanded_line, style)] # Fallback
        else:
            content_segments = [Segment(expanded_line, style)]

        # Add cursor if it's the active line
        if line_index == self.cursor_line:
            content_segments = self._add_cursor_to_segments(content_segments, line)

        # --- Final Assembly ---
        if scroll_x > 0:
            content_segments = self._apply_horizontal_scroll(content_segments, scroll_x)
            
        available_width = self.size.width - line_number_width
        truncated_content = self._truncate_segments_to_width(content_segments, available_width)

        final_segments = line_number_segments + truncated_content
        return Strip(final_segments, self.size.width)
    
    def load_file(self, file_path: Union[str, Path]) -> bool:
        """Load a file into the editor."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                # Create new file
                self.text = ""
                self.current_file = path
                self.is_modified = False
                return True
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.text = content
            self.current_file = path
            self.is_modified = False
            
            # Set language based on file extension
            extension = path.suffix.lower()
            language = self._language_map.get(extension)
            
            if language:
                self._syntax_language = language
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.info(f"CUSTOM EDITOR: Using syntax highlighting for language: {language}")
            else:
                self._syntax_language = "text" # Default to plain text
                if self._app_instance and hasattr(self._app_instance, 'logger'):
                    self._app_instance.logger.info("CUSTOM EDITOR: No language mapping found, using plain text highlighting")
            
            if self._app_instance and hasattr(self._app_instance, 'logger'):
                self._app_instance.logger.info(f"CUSTOM EDITOR: Successfully loaded file: {path}")
            
            # Force a refresh and update virtual size
            self.update_virtual_size()
            self.refresh()
            return True
            
        except Exception as e:
            if self._app_instance and hasattr(self._app_instance, 'logger'):
                self._app_instance.logger.error(f"CUSTOM EDITOR: Error loading file {file_path}: {e}", exc_info=True)
            return False
    
    def action_cursor_up(self) -> None:
        """Move cursor up one line."""
        if self.cursor_line > 0:
            self.cursor_line -= 1
            self._clamp_cursor()
            self._ensure_cursor_visible()
            self.refresh()
    
    def action_cursor_down(self) -> None:
        """Move cursor down one line."""
        lines = self.text.split('\n')
        if self.cursor_line < len(lines) - 1:
            self.cursor_line += 1
            self._clamp_cursor()
            self._ensure_cursor_visible()
            self.refresh()
    
    def action_cursor_left(self) -> None:
        """Move cursor left one character."""
        if self.cursor_column > 0:
            self.cursor_column -= 1
        elif self.cursor_line > 0:
            self.cursor_line -= 1
            lines = self.text.split('\n')
            self.cursor_column = len(lines[self.cursor_line]) if self.cursor_line < len(lines) else 0
        self._ensure_cursor_visible()
        self.refresh()
    
    def action_cursor_right(self) -> None:
        """Move cursor right one character."""
        lines = self.text.split('\n')
        if self.cursor_line < len(lines):
            line_length = len(lines[self.cursor_line])
            if self.cursor_column < line_length:
                self.cursor_column += 1
            elif self.cursor_line < len(lines) - 1:
                self.cursor_line += 1
                self.cursor_column = 0
        self._ensure_cursor_visible()
        self.refresh()
    
    def action_cursor_home(self) -> None:
        """Move cursor to start of line."""
        self.cursor_column = 0
        self.refresh()
    
    def action_cursor_end(self) -> None:
        """Move cursor to end of line."""
        lines = self.text.split('\n')
        if self.cursor_line < len(lines):
            self.cursor_column = len(lines[self.cursor_line])
        self.refresh()
    
    def action_page_up(self) -> None:
        """Move cursor up one page."""
        page_size = self.size.height - 1
        self.cursor_line = max(0, self.cursor_line - page_size)
        self._clamp_cursor()
        self._ensure_cursor_visible()
        self.refresh()
    
    def action_page_down(self) -> None:
        """Move cursor down one page."""
        lines = self.text.split('\n')
        page_size = self.size.height - 1
        self.cursor_line = min(len(lines) - 1, self.cursor_line + page_size)
        self._clamp_cursor()
        self._ensure_cursor_visible()
        self.refresh()
    
    def action_scroll_up(self) -> None:
        """Scroll up without moving cursor."""
        scroll_x, scroll_y = self.scroll_offset
        new_scroll_y = max(0, scroll_y - 3)  # Scroll up by 3 lines
        self.scroll_to(scroll_x, new_scroll_y, animate=False)
    
    def _render_welcome_screen(self, y: int) -> Strip:
        """Render a welcome screen when no file is loaded."""
        height = self.size.height
        width = self.size.width
        
        # Make the welcome screen more compact to avoid overlapping issues
        welcome_lines = [
            "",
            "  ╭─────────────────────────────────────────────╮",
            "  │                                             │",
            "  │         K2Edit - Code Editor                │",
            "  │                                             │",
            "  │  Press Ctrl+O to open a file                │",
            "  │  Use file explorer (left) to browse         │",
            "  │  Press Ctrl+K for command bar             │",
            "  │                                             │",
            "  ╰─────────────────────────────────────────────╯",
            "",
            "  Ready to edit! Select a file to begin."
        ]
        
        # Position it higher to avoid any potential overlap
        center_y = max(height // 3, 5)  # Position in upper third of screen
        start_y = center_y
        
        if y < start_y or y >= start_y + len(welcome_lines):
            return Strip.blank(width)
        
        line_index = y - start_y
        if line_index < 0 or line_index >= len(welcome_lines):
            return Strip.blank(width)
        
        line = welcome_lines[line_index]
        
        # Center the line horizontally
        if len(line) < width:
            padding = max(0, (width - len(line)) // 2)
            centered_line = " " * padding + line
        else:
            centered_line = line[:width]
        
        # Use more subtle styling
        if "K2Edit" in line:
            style = Style(color="#60a5fa", bold=True)  # Blue for title
        elif line.strip().startswith("╭") or line.strip().startswith("│") or line.strip().startswith("╰"):
            style = Style(color="#475569")  # Gray for borders
        else:
            style = Style(color="#94a3b8")  # Lighter gray for text
        
        segments = [Segment(centered_line, style)]
        return Strip(segments, width)

    def action_scroll_down(self) -> None:
        """Scroll down without moving cursor."""
        scroll_x, scroll_y = self.scroll_offset
        max_scroll_y = max(0, self.get_content_height() - self.size.height)
        new_scroll_y = min(max_scroll_y, scroll_y + 3)  # Scroll down by 3 lines
        self.scroll_to(scroll_x, new_scroll_y, animate=False)
    
    def get_selected_text(self) -> Optional[str]:
        """Get the currently selected text. Returns None if no selection."""
        # For now, return None as we don't have selection implemented
        # This can be extended later to support actual text selection
        return None
    
    @property
    def cursor_location(self) -> dict:
        """Get cursor location as a dictionary with line and column."""
        return {"line": self.cursor_line, "column": self.cursor_column}
    
    @property
    def selection(self):
        """Placeholder selection object for AI integration compatibility."""
        class DummySelection:
            is_empty = True
        return DummySelection()
    
    def get_selected_lines(self):
        """Placeholder method for AI integration compatibility."""
        return (0, 0)
    
    def _clamp_cursor(self) -> None:
        """Ensure cursor is within valid bounds."""
        lines = self.text.split('\n')
        if not lines:
            self.cursor_line = 0
            self.cursor_column = 0
            return
        
        # Clamp line
        self.cursor_line = max(0, min(self.cursor_line, len(lines) - 1))
        
        # Clamp column
        if self.cursor_line < len(lines):
            line_length = len(lines[self.cursor_line])
            self.cursor_column = max(0, min(self.cursor_column, line_length))
    
    def _ensure_cursor_visible(self) -> None:
        """Ensure the cursor is visible by adjusting scroll position."""
        # Use Textual's built-in scrolling to ensure cursor is visible
        cursor_y = self.cursor_line
        cursor_x = self.cursor_column
        
        # Don't add line number offset - line numbers are fixed and don't scroll
        # Only scroll the content area
        
        # Scroll to make cursor visible
        self.scroll_to(cursor_x, cursor_y, animate=False)
    
    def on_focus(self, event) -> None:
        if self._app_instance and hasattr(self._app_instance, 'logger'):
            self._app_instance.logger.info("Editor focused, forcing full refresh")
        self.refresh(layout=True)

    def on_blur(self, event) -> None:
        if self._app_instance and hasattr(self._app_instance, 'logger'):
            self._app_instance.logger.info("Editor blurred")

    def on_click(self, event: Click) -> None:
        """Handle mouse clicks to position cursor."""
        if self._app_instance and hasattr(self._app_instance, 'logger'):
            self._app_instance.logger.info(f"Editor clicked at {event.x}, {event.y}")
        # Calculate line and column from click position
        scroll_x, scroll_y = self.scroll_offset
        click_line = event.y + scroll_y
        click_column = event.x
        
        # Adjust for line numbers
        if self.show_line_numbers:
            line_number_area_width = self._line_number_width + 3  # line number + space + separator
            if click_column >= line_number_area_width:
                click_column -= line_number_area_width
            else:
                click_column = 0
        
        lines = self.text.split('\n')
        if click_line < len(lines):
            self.cursor_line = click_line
            self.cursor_column = min(click_column, len(lines[click_line]))
            self._clamp_cursor()
        self.refresh()
        self.focus()
    
    def save_file(self, file_path: Optional[Union[str, Path]] = None) -> bool:
        """Save the current content to a file."""
        try:
            if file_path:
                path = Path(file_path)
            elif self.current_file:
                path = self.current_file
            else:
                return False
            
            # Read old content for agentic system
            old_content = ""
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.text)
            
            # Notify agentic system of file change
            if self._app_instance and hasattr(self._app_instance, '_on_file_change_with_agent'):
                import asyncio
                asyncio.create_task(
                    self._app_instance._on_file_change_with_agent(
                        str(path), old_content, self.text
                    )
                )
            
            self.current_file = path
            self.is_modified = False
            return True
            
        except Exception as e:
            if self._app_instance and hasattr(self._app_instance, 'logger'):
                self._app_instance.logger.error(f"CUSTOM EDITOR: Error saving file: {e}")
            return False