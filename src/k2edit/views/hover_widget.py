#!/usr/bin/env python3
"""Hover widget for displaying LSP hover information."""

from typing import Optional, Dict, Any
from pathlib import Path

from textual.widgets import Markdown
from textual.containers import Container
from textual.widget import Widget
from textual.reactive import reactive
from textual.geometry import Size, Region
from textual.strip import Strip
from textual.color import Color

from ..logger import get_logger


class HoverWidget(Widget):
    """A floating widget to display LSP hover information."""
 
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._content = ""
        self._visible = False
        self._markdown = None
        # Explicitly set overlay to 'none' to avoid any default 'cursor' value
        self.styles.overlay = "none"
        self.styles.position = "absolute"

    def compose(self):
        """Compose the hover widget."""
        self._markdown = Markdown(self._content)
        yield Container(self._markdown)
    
    def show_hover(self, content: str, line: int, column: int, editor=None) -> None:
        """Show hover content near the cursor position."""
        logger = get_logger()
        logger.debug(f"HoverWidget.show_hover: line={line}, column={column}, content_length={len(content)}")
        
        self._content = content
        self._visible = True
        
        if self._markdown:
            self._markdown.update(self._content)
        
        self.add_class("visible")
        self.remove_class("hidden")
        self.styles.display = "block"
        
        # Calculate absolute position based on editor region and cursor location
        # Get editor's screen region
        editor_region = editor.region
        
        # Safely get cursor location with error handling
        try:
            cursor_location = editor.cursor_location
            if isinstance(cursor_location, (tuple, list)) and len(cursor_location) >= 2:
                cursor_line, cursor_column = cursor_location[0], cursor_location[1]
            else:
                logger.error(f"Invalid cursor_location format: {cursor_location}")
                return
        except Exception as e:
            logger.error(f"Error getting cursor location: {e}")
            return
        
        logger.debug(f"Editor region: {editor_region}")
        logger.debug(f"Cursor location: line={cursor_line}, column={cursor_column}")
        logger.debug(f"Raw cursor_location: {cursor_location}")
        
        # Calculate absolute screen coordinates
        # Add editor's position to cursor position, accounting for scroll offset
        scroll_offset = editor.scroll_offset
        logger.debug(f"Editor scroll offset: {scroll_offset}")
        
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
        logger.debug(f"Widget size: {self.size}, height: {widget_height}")
        
        # If widget still has no height after refresh, calculate based on content
        if widget_height <= 0:
            # Count lines in content to estimate height
            content_lines = len(content.split('\n'))
            widget_height = content_lines + 2  # Add padding for borders/margins
            logger.debug(f"Widget height calculated from content lines: {content_lines} -> height: {widget_height}")
        
        hover_y = max(0, absolute_y - widget_height - 1)  # Position above cursor with widget height offset
        logger.debug(f"Positioning: absolute_y={absolute_y}, widget_height={widget_height}, final hover_y={hover_y}")
        
        # Use absolute positioning with screen overlay
        # The offset is relative to the screen origin (0,0) when using overlay="screen"
        self.styles.overlay = "screen"
        self.styles.position = "absolute"
        self.styles.offset = (hover_x, hover_y)
        
        # Set anchor to top-left (default) so offset positions from widget's top-left corner
        # This ensures the widget appears above the cursor, not centered on it
        self.styles.text_align = "left"
        self.styles.content_align = "left top"
        
        logger.debug(f"Hover positioned at absolute coordinates: ({hover_x}, {hover_y})")
        logger.debug(f"Calculated from editor region ({editor_region.x}, {editor_region.y}) + visible cursor ({visible_cursor_column}, {visible_cursor_line})")
        logger.debug(f"Original cursor ({cursor_column}, {cursor_line}) adjusted by scroll offset ({scroll_offset.x}, {scroll_offset.y})")
        
    def hide_hover(self) -> None:
        """Hide the hover widget."""
        logger = get_logger()
        logger.debug("HoverWidget.hide_hover called")
        
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