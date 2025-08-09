"""Shared initialization utilities for K2Edit."""

import asyncio
from pathlib import Path
from typing import Optional, Callable, Any
from aiologger import Logger

from ..agent.integration import K2EditAgentIntegration
# Removed error_handler import - using basic exception handling
from .config import get_config


class AgentInitializer:
    """Handles agent system initialization with proper error handling and progress reporting."""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.config = get_config()
    
    async def initialize_agent_system(
        self,
        project_root: str,
        diagnostics_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        command_bar=None,
        output_panel=None,
        current_file: Optional[str] = None
    ) -> Optional[K2EditAgentIntegration]:
        """Initialize the agentic system with standardized error handling."""
        
        try:
            await self.logger.info("Initializing agentic system...")
            
            # Create agent integration
            agent_integration = K2EditAgentIntegration(
                project_root, 
                self.logger, 
                diagnostics_callback
            )
            
            # Initialize with progress updates
            await agent_integration.initialize(progress_callback)
            
            # Update command bar if provided
            if command_bar and hasattr(command_bar, 'set_agent_integration'):
                command_bar.set_agent_integration(agent_integration)
            
            # Add welcome message if output panel provided
            if output_panel and hasattr(output_panel, 'add_welcome_message'):
                output_panel.add_welcome_message()
            
            await self.logger.info("Agentic system initialized successfully")
            
            # Handle current file if provided
            if current_file and agent_integration:
                await self._handle_current_file(agent_integration, current_file)
            
            return agent_integration
            
        except Exception as e:
            await self.logger.error(f"Failed to initialize agentic system: {e}", exc_info=True)
            return None
    
    async def _handle_current_file(
        self, 
        agent_integration: K2EditAgentIntegration, 
        current_file: str
    ):
        """Handle current file notification to agent system."""
        try:
            await self.logger.info(f"Notifying LSP server about current file: {current_file}")
            await self._notify_file_opened(agent_integration, current_file)
        except Exception as e:
            await self.logger.warning(f"Failed to notify agent about current file {current_file}: {e}", exc_info=True)
    
    async def _notify_file_opened(
        self, 
        agent_integration: K2EditAgentIntegration, 
        file_path: str
    ):
        """Notify agent integration about file being opened."""
        if not agent_integration:
            return
        
        # Notify agent about file open
        await agent_integration.on_file_open(file_path)
        
        # Start language server if needed
        if agent_integration.lsp_client:
            await self._start_language_server_if_needed(agent_integration, file_path)
        
        # Notify LSP about opened file
        if agent_integration.lsp_client:
            await agent_integration.lsp_client.notify_file_opened(file_path)
    
    async def _start_language_server_if_needed(
        self, 
        agent_integration: K2EditAgentIntegration, 
        file_path: str
    ):
        """Start language server if not already running for the file's language."""
        try:
            from ..agent.language_configs import LanguageConfigs
            from .language_utils import detect_language_by_extension
            
            language = detect_language_by_extension(Path(file_path).suffix)
            
            if (language != "unknown" and 
                not agent_integration.lsp_client.is_server_running(language)):
                
                await self.logger.info(
                    f"Starting {language} language server for opened file: {file_path}"
                )
                
                config = LanguageConfigs.get_config(language)
                await agent_integration.lsp_client.start_server(
                    language, 
                    config["command"], 
                    str(agent_integration.project_root)
                )
                await agent_integration.lsp_client.initialize_connection(
                    language, 
                    str(agent_integration.project_root)
                )
                
                await self.logger.info(f"Started {language} language server successfully")
                
        except Exception as e:
            await self.logger.error(f"Failed to start language server: {e}")





def create_agent_initializer(logger: Logger) -> AgentInitializer:
    """Factory function to create an agent initializer."""
    return AgentInitializer(logger)