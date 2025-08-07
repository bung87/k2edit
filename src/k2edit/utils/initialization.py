"""Shared initialization utilities for K2Edit."""

import asyncio
from pathlib import Path
from typing import Optional, Callable, Any
from aiologger import Logger

from ..agent.integration import K2EditAgentIntegration
from .error_handler import ErrorHandler, AgentSystemError
from .config import get_config


class AgentInitializer:
    """Handles agent system initialization with proper error handling and progress reporting."""
    
    def __init__(self, logger: Logger, error_handler: ErrorHandler):
        self.logger = logger
        self.error_handler = error_handler
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
            error = AgentSystemError(
                f"Failed to initialize agentic system: {e}",
                context={"project_root": project_root, "current_file": current_file}
            )
            await self.error_handler.handle_error(
                error, 
                user_message="Agentic system initialization failed"
            )
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
            await self.error_handler.handle_error(
                e,
                context={"current_file": current_file},
                user_message=f"Failed to notify agent about current file: {current_file}"
            )
    
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


class FileInitializer:
    """Handles file initialization with proper error handling."""
    
    def __init__(self, logger: Logger, error_handler: ErrorHandler):
        self.logger = logger
        self.error_handler = error_handler
    
    async def initialize_file(
        self,
        file_path: str,
        editor,
        output_panel=None,
        on_file_open_callback: Optional[Callable[[str], Any]] = None
    ) -> bool:
        """Initialize a file with proper error handling."""
        
        try:
            path = Path(file_path)
            
            if path.is_file():
                return await self._load_existing_file(
                    file_path, editor, output_panel, on_file_open_callback
                )
            elif path.is_dir():
                await self._handle_directory_path(file_path, output_panel)
                return False
            else:
                return await self._create_new_file(
                    file_path, editor, output_panel
                )
                
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                context={"file_path": file_path},
                user_message=f"Failed to initialize file: {file_path}"
            )
            return False
    
    async def _load_existing_file(
        self, 
        file_path: str, 
        editor, 
        output_panel, 
        on_file_open_callback
    ) -> bool:
        """Load an existing file."""
        await self.logger.info(f"Loading existing file: {file_path}")
        
        success = await editor.load_file(file_path)
        if success:
            if output_panel:
                output_panel.add_info(f"Loaded file: {file_path}")
            await self.logger.info(f"Successfully loaded file: {file_path}")
            
            if on_file_open_callback:
                await on_file_open_callback(file_path)
            
            return True
        else:
            error_msg = f"Failed to load file: {file_path}"
            if output_panel:
                output_panel.add_error(error_msg)
            await self.logger.error(error_msg)
            return False
    
    async def _handle_directory_path(self, file_path: str, output_panel):
        """Handle case where provided path is a directory."""
        await self.logger.warning(f"Path is a directory, not a file: {file_path}")
        if output_panel:
            output_panel.add_warning(f"Cannot open a directory: {file_path}")
    
    async def _create_new_file(self, file_path: str, editor, output_panel) -> bool:
        """Create a new file."""
        await self.logger.info(f"File does not exist, creating new file: {file_path}")
        
        editor.load_file(file_path)  # This will create a new buffer
        if output_panel:
            output_panel.add_info(f"New file: {file_path}")
        
        return True


def create_agent_initializer(logger: Logger, error_handler: ErrorHandler) -> AgentInitializer:
    """Factory function to create an agent initializer."""
    return AgentInitializer(logger, error_handler)


def create_file_initializer(logger: Logger, error_handler: ErrorHandler) -> FileInitializer:
    """Factory function to create a file initializer."""
    return FileInitializer(logger, error_handler)