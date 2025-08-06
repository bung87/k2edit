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


class HoverWidget(Widget):
    """A floating widget to display LSP hover information."""
    
    DEFAULT_CSS = """
    HoverWidget {
        width: auto;
        height: auto;
        max-width: 60;
        max-height: 20;
        background: $surface;
        border: solid $primary;
        border-title-color: $primary;
        padding: 1;
        layer: overlay;
        offset: 0 0;
        display: none;
    }
    
    HoverWidget.visible {
        display: block;
    }
    
    HoverWidget > Markdown {
        margin: 0;
        padding: 0;
    }
    
    HoverWidget .markdown {
        margin: 0;
        padding: 0;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._content = ""
        self._visible = False
        self._markdown = None
        
    def compose(self):
        """Compose the hover widget."""
        self._markdown = Markdown(self._content)
        yield Container(self._markdown)
    
    def show_hover(self, content: str, line: int, column: int) -> None:
        """Show hover content near the cursor position."""
        import logging
        logger = logging.getLogger("k2edit")
        logger.debug(f"HoverWidget.show_hover: line={line}, column={column}, content_length={len(content)}")
        
        self._content = content
        self._visible = True
        
        if self._markdown:
            self._markdown.update(self._content)
        
        self.add_class("visible")
        self.remove_class("hidden")
        self.styles.display = "block"
        
        # Position relative to cursor using Textual's overlay system
        self.styles.offset = (column + 2, line + 1)
        logger.debug(f"Hover positioned at offset: {self.styles.offset}")
        
    def hide_hover(self) -> None:
        """Hide the hover widget."""
        import logging
        logger = logging.getLogger("k2edit")
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