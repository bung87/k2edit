#!/usr/bin/env python3
"""Settings manager for K2Edit AI model configurations."""

import json
import os
import asyncio
from pathlib import Path
from typing import Dict, Tuple
from urllib.parse import urlparse
import aiofiles
from .async_performance_utils import io_bound_task


class SettingsManager:
    """Manages AI model settings for K2Edit."""
    
    # Default API endpoints for each model
    DEFAULT_ENDPOINTS = {
        "openai": "https://api.openai.com/v1",
        "claude": "https://api.anthropic.com",
        "gemini": "https://generativelanguage.googleapis.com",
        "mistral": "https://api.mistral.ai/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "moonshot_china": "https://api.moonshot.cn/v1",
        "moonshot_international": "https://api.moonshot.ai/v1",
        "local": "http://localhost:11434/api"
    }
    
    # Model display names
    MODEL_NAMES = {
        "openai": "OpenAI GPT",
        "claude": "Anthropic Claude",
        "gemini": "Google Gemini",
        "mistral": "Mistral/Mixtral",
        "openrouter": "OpenRouter",
        "moonshot_china": "Moonshot AI (China)",
        "moonshot_international": "Moonshot AI (International)",
        "local": "Local Models (LM Studio/Ollama)"
    }
    
    def __init__(self):
        self.settings_file = self._get_settings_file_path()
        self.settings = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize settings asynchronously."""
        if not self._initialized:
            self.settings = await self._load_settings()
            self._initialized = True
    
    def _get_settings_file_path(self) -> Path:
        """Get the cross-platform settings file path."""
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('USERPROFILE', Path.home()))
        else:  # Unix-like (Linux, macOS)
            base_dir = Path.home()
        
        settings_dir = base_dir / '.k2edit'
        settings_dir.mkdir(exist_ok=True)
        return settings_dir / 'settings.json'
    
    async def _load_settings(self) -> Dict[str, Dict[str, str]]:
        """Load settings from file or create default settings using async I/O."""
        if self.settings_file.exists():
            try:
                async with aiofiles.open(self.settings_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    return await asyncio.to_thread(json.loads, content)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted, create default settings
                pass
        
        # Create default settings
        default_settings = {}
        for model_id, endpoint in self.DEFAULT_ENDPOINTS.items():
            default_settings[model_id] = {
                "api_address": endpoint,
                "api_key": ""
            }
        
        await self._save_settings(default_settings)
        return default_settings
    
    async def _save_settings(self, settings: Dict[str, Dict[str, str]]) -> None:
        """Save settings to file using async I/O."""
        try:
            # Use asyncio.to_thread for JSON serialization to avoid blocking
            json_content = await asyncio.to_thread(
                json.dumps, settings, indent=2, ensure_ascii=False
            )
            async with aiofiles.open(self.settings_file, 'w', encoding='utf-8') as f:
                await f.write(json_content)
        except IOError as e:
            raise RuntimeError(f"Failed to save settings: {e}")
    
    async def get_api_settings(self, model_name: str) -> Tuple[str, str]:
        """Get API settings for a specific model.
        
        Args:
            model_name: The model identifier
            
        Returns:
            Tuple of (api_address, api_key)
        """
        # Ensure settings are initialized
        await self.initialize()
        
        if model_name not in self.settings:
            # Return default if model not found
            default_endpoint = self.DEFAULT_ENDPOINTS.get(model_name, "")
            return (default_endpoint, "")
        
        model_settings = self.settings[model_name]
        return (model_settings.get("api_address", ""), model_settings.get("api_key", ""))
    
    async def save_model_settings(self, model_name: str, api_address: str, api_key: str) -> Tuple[bool, str]:
        """Save settings for a specific model using async I/O.
        
        Args:
            model_name: The model identifier
            api_address: The API endpoint URL
            api_key: The API key
            
        Returns:
            Tuple of (success, error_message)
        """
        # Ensure settings are initialized
        await self.initialize()
        
        # Validate API address
        if not self._validate_url(api_address):
            return (False, "Invalid API address. Please enter a valid URL.")
        
        # Update settings
        if model_name not in self.settings:
            self.settings[model_name] = {}
        
        self.settings[model_name]["api_address"] = api_address.strip()
        self.settings[model_name]["api_key"] = api_key.strip()
        
        try:
            await self._save_settings(self.settings)
            return (True, "Settings saved successfully.")
        except RuntimeError as e:
            return (False, str(e))
    
    def _validate_url(self, url: str) -> bool:
        """Validate if a string is a valid URL."""
        if not url or not url.strip():
            return False
        
        try:
            result = urlparse(url.strip())
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def get_all_models(self) -> Dict[str, str]:
        """Get all available models with their display names."""
        return self.MODEL_NAMES.copy()
    
    def get_model_display_name(self, model_id: str) -> str:
        """Get the display name for a model ID."""
        return self.MODEL_NAMES.get(model_id, model_id)
    
    async def reset_model_to_default(self, model_name: str) -> None:
        """Reset a model's settings to default values using async I/O."""
        # Ensure settings are initialized
        await self.initialize()
        
        if model_name in self.DEFAULT_ENDPOINTS:
            self.settings[model_name] = {
                "api_address": self.DEFAULT_ENDPOINTS[model_name],
                "api_key": ""
            }
            await self._save_settings(self.settings)