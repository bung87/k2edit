#!/usr/bin/env python3
"""Settings modal for K2Edit AI model configuration."""

from typing import Optional
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Label, Select, Input
from textual.binding import Binding
from textual.message import Message
from aiologger import Logger

from ..utils.settings_manager import SettingsManager


class SettingsModal(ModalScreen[None]):
    """Modal screen for configuring AI model settings."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("ctrl+s", "save_settings", "Save"),
    ]
    
    class SettingsSaved(Message):
        """Message sent when settings are saved."""
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name
            super().__init__()
    
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.settings_manager = SettingsManager()
        self.current_model = "openai"  # Default selected model
        self.model_select: Optional[Select] = None
        self.api_address_input: Optional[Input] = None
        self.api_key_input: Optional[Input] = None
        self.status_label: Optional[Static] = None
    
    async def _log_debug(self, message: str):
        """Log debug message asynchronously"""
        await self.logger.debug(message)
    
    async def _log_error(self, message: str):
        """Log error message asynchronously"""
        await self.logger.error(message)
    
    def compose(self) -> ComposeResult:
        """Compose the settings modal."""
        with Container(id="settings-modal"):
            yield Static("AI Model Settings", id="settings-title")
            
            with Vertical(id="settings-content"):
                # Model selection
                yield Label("Select AI Model:")
                model_options = [(display_name, model_id) for model_id, display_name in self.settings_manager.get_all_models().items()]
                self.model_select = Select(model_options, value=self.current_model, id="model-select")
                yield self.model_select
                
                # API Address input
                yield Label("API Address:")
                api_address, _ = self.settings_manager.get_api_settings(self.current_model)
                self.api_address_input = Input(
                    value=api_address,
                    placeholder="Enter API endpoint URL",
                    id="api-address-input"
                )
                yield self.api_address_input
                
                # API Key input
                yield Label("API Key:")
                _, api_key = self.settings_manager.get_api_settings(self.current_model)
                self.api_key_input = Input(
                    value=api_key,
                    placeholder="Enter API key (leave empty if not required)",
                    password=True,
                    id="api-key-input"
                )
                yield self.api_key_input
                
                # Status message
                self.status_label = Static("", id="settings-status")
                yield self.status_label
                
                # Action buttons
                with Horizontal(id="settings-buttons"):
                    yield Button("Save", variant="primary", id="save-button")
                    yield Button("Reset to Default", variant="default", id="reset-button")
                    yield Button("Cancel", variant="default", id="cancel-button")
    
    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle model selection change."""
        if event.select.id == "model-select" and event.value != Select.BLANK:
            await self._load_model_settings(str(event.value))
    
    async def _load_model_settings(self, model_id: str) -> None:
        """Load settings for the selected model."""
        self.current_model = model_id
        api_address, api_key = self.settings_manager.get_api_settings(model_id)
        
        if self.api_address_input:
            self.api_address_input.value = api_address
        if self.api_key_input:
            self.api_key_input.value = api_key
        
        # Clear status message
        if self.status_label:
            self.status_label.update("")
        
        await self._log_debug(f"Loaded settings for model: {model_id}")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save-button":
            await self.action_save_settings()
        elif event.button.id == "reset-button":
            await self._reset_to_default()
        elif event.button.id == "cancel-button":
            self.dismiss()
    
    async def action_save_settings(self) -> None:
        """Save the current settings."""
        if not self.api_address_input or not self.api_key_input:
            return
        
        api_address = self.api_address_input.value.strip()
        api_key = self.api_key_input.value.strip()
        
        # Validate inputs
        if not api_address:
            await self._show_status("API address cannot be empty.", "error")
            return
        
        # Save settings
        success, message = self.settings_manager.save_model_settings(
            self.current_model, api_address, api_key
        )
        
        if success:
            await self._show_status(message, "success")
            await self._log_debug(f"Settings saved for model: {self.current_model}")
            
            # Post message to notify other components
            self.post_message(self.SettingsSaved(self.current_model))
        else:
            await self._show_status(message, "error")
            await self._log_error(f"Failed to save settings for {self.current_model}: {message}")
    
    async def _reset_to_default(self) -> None:
        """Reset current model settings to default values."""
        self.settings_manager.reset_model_to_default(self.current_model)
        await self._load_model_settings(self.current_model)
        await self._show_status("Settings reset to default values.", "success")
        await self._log_debug(f"Reset settings to default for model: {self.current_model}")
    
    async def _show_status(self, message: str, status_type: str = "info") -> None:
        """Show a status message."""
        if self.status_label:
            # Add CSS class based on status type
            css_class = f"settings-status-{status_type}"
            self.status_label.set_class(css_class)
            self.status_label.update(message)
            
            # Clear the message after 3 seconds
            self.set_timer(3.0, lambda: self.status_label.update("") if self.status_label else None)