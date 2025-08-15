#!/usr/bin/env python3
"""Hover widget for displaying LSP hover information."""

from textual.widgets import Markdown
from textual.containers import Container
from textual.widget import Widget
from ..logger import Logger


class HoverWidget(Widget):
    """A floating widget to display LSP hover information."""
 
    
    def __init__(self, logger=None, **kwargs):
        super().__init__(**kwargs)
        self._content = ""
        self._visible = False
        self._markdown = None
        self.logger = logger or Logger(name="k2edit")
        # Explicitly set overlay to 'none' to avoid any default 'cursor' value
        self.styles.overlay = "none"
        self.styles.position = "absolute"

    def compose(self):
        """Compose the hover widget."""
        self._markdown = Markdown(self._content)
        yield Container(self._markdown)
    
    async def show_hover(self, content: str, line: int, column: int, editor=None) -> None:
        """Show hover content near the cursor position."""

        self._content = content
        self._visible = True
        
        if self._markdown:
            self._markdown.update(self._content)
        
        self.add_class("visible")
        self.remove_class("hidden")
        self.styles.display = "block"
        
        # Calculate absolute position based on editor region and provided cursor location
        # Get editor's screen region
        editor_region = editor.region
        
        # Use the provided cursor position parameters
        cursor_line, cursor_column = line, column
        
        await self.logger.debug(f"Editor region: {editor_region}")
        await self.logger.debug(f"Cursor location: line={cursor_line}, column={cursor_column}")
        
        # Calculate absolute screen coordinates
        # Add editor's position to cursor position, accounting for scroll offset
        scroll_offset = editor.scroll_offset
        await self.logger.debug(f"Editor scroll offset: {scroll_offset}")
        
        # Adjust cursor position by scroll offset
        visible_cursor_line = cursor_line - scroll_offset.y
        visible_cursor_column = cursor_column - scroll_offset.x
        
        absolute_x = editor_region.x + visible_cursor_column
        absolute_y = editor_region.y + visible_cursor_line
        
        # Position hover widget slightly offset from cursor
        hover_x = absolute_x + 1
        
        # Force widget to measure itself to get accurate height
        self.refresh(layout=True)
        
        # Get widget height to position it properly above cursor
        widget_height = self.size.height

        # If widget still has no height after refresh, calculate based on content
        if widget_height <= 0:
            # Count lines in content to estimate height
            content_lines = len(content.split('\n'))
            widget_height = content_lines + 2  # Add padding for borders/margins
            await self.logger.debug(f"Widget height calculated from content lines: {content_lines} -> height: {widget_height}")
        
        hover_y = max(0, absolute_y - widget_height - 1)  # Position above cursor with widget height offset
        await self.logger.debug(f"Positioning: absolute_y={absolute_y}, widget_height={widget_height}, final hover_y={hover_y}")
        
        # Use absolute positioning with screen overlay
        # The offset is relative to the screen origin (0,0) when using overlay="screen"
        self.styles.overlay = "screen"
        self.styles.position = "absolute"
        self.styles.offset = (hover_x, hover_y)
        
        # Set anchor to top-left (default) so offset positions from widget's top-left corner
        # This ensures the widget appears above the cursor, not centered on it
        self.styles.text_align = "left"
        self.styles.content_align = "left top"
        
        await self.logger.debug(f"Hover positioned at absolute coordinates: ({hover_x}, {hover_y})")
        await self.logger.debug(f"Calculated from editor region ({editor_region.x}, {editor_region.y}) + visible cursor ({visible_cursor_column}, {visible_cursor_line})")
        await self.logger.debug(f"Original cursor ({cursor_column}, {cursor_line}) adjusted by scroll offset ({scroll_offset.x}, {scroll_offset.y})")
        
    async def hide_hover(self) -> None:
        """Hide the hover widget."""

        self._visible = False
        self.remove_class("visible")
        self.add_class("hidden")
        self.styles.display = "none"
    
    def is_visible(self) -> bool:
        """Check if the hover widget is currently visible."""
        return self._visible
    
    def get_content(self) -> str:
        """Get the current hover content."""
        return self._content