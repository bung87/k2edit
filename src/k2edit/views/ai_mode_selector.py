"""AI Mode Selector widget for choosing between ask and agent modes."""

from textual.app import ComposeResult
from textual.widgets import Select
from textual.widget import Widget
from textual.message import Message


class AIModeSelector(Widget):
    """Widget for selecting AI interaction mode."""
    
    class ModeSelected(Message):
        """Message sent when a mode is selected."""
        def __init__(self, mode: str) -> None:
            self.mode = mode
            super().__init__()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_mode = "ask"  # Default mode
    
    def compose(self) -> ComposeResult:
        """Compose the AI mode selector."""
        options = [("Ask", "ask"), ("Agent", "agent")]
        yield Select(options, value="ask", id="ai-mode-selector")
    
    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select change events."""
        self.current_mode = event.value
        self.post_message(self.ModeSelected(event.value))