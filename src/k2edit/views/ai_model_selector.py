#!/usr/bin/env python3
"""AI Model Selector widget for choosing between different AI models."""

from textual.app import ComposeResult
from textual.widgets import Select
from textual.widget import Widget
from textual.message import Message
from aiologger import Logger

from ..utils.settings_manager import SettingsManager


class AIModelSelector(Widget):
    """Widget for selecting AI model."""
    
    class ModelSelected(Message):
        """Message sent when a model is selected."""
        def __init__(self, model_id: str, model_name: str) -> None:
            self.model_id = model_id
            self.model_name = model_name
            super().__init__()
    
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.settings_manager = SettingsManager()
        self.current_model = "openai"  # Default model
    
    def compose(self) -> ComposeResult:
        """Compose the AI model selector."""
        # Get all available models
        models = self.settings_manager.get_all_models()
        options = [(display_name, model_id) for model_id, display_name in models.items()]
        
        yield Select(options, value="openai", id="ai-model-selector", compact=True)
    
    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select change events."""
        if event.select.id == "ai-model-selector" and event.value != Select.BLANK:
            self.current_model = str(event.value)
            model_name = self.settings_manager.get_model_display_name(self.current_model)
            await self.logger.info(f"AI model changed to: {model_name} ({self.current_model})")
            self.post_message(self.ModelSelected(self.current_model, model_name))
    
    def get_current_model(self) -> str:
        """Get the currently selected model ID."""
        return self.current_model
    
    def set_model(self, model_id: str) -> None:
        """Set the current model programmatically."""
        if model_id in self.settings_manager.get_all_models():
            self.current_model = model_id
            # Update the select widget if it exists
            select_widget = self.query_one("#ai-model-selector", Select)
            if select_widget:
                select_widget.value = model_id