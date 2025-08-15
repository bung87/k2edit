"""
K2Edit Agentic System Integration

This module provides simple integration hooks for the existing K2Edit application
to add agentic context, memory, and LSP indexing capabilities.
"""

import asyncio
from aiologger import Logger
from pathlib import Path
from typing import Optional, Dict, Any

from . import (
    initialize_agentic_system,
    process_agent_query,
    record_code_change,
    get_code_intelligence,
    shutdown_agentic_system
)
from .lsp_client import LSPClient
from .language_configs import LanguageConfigs
from .file_filter import FileFilter
from ..utils.language_utils import detect_project_language

class K2EditAgentIntegration:
    """Simple integration class for K2Edit agentic system"""
    
    def __init__(self, project_root: str, logger: Logger, diagnostics_callback=None, show_message_callback=None):
        self.project_root = Path(project_root)
        self.logger = logger
        self.agent_initialized = False
        self._lsp_indexer = None
        self.diagnostics_callback = diagnostics_callback
        self.show_message_callback = show_message_callback
        self.lsp_client = LSPClient(logger=self.logger, diagnostics_callback=diagnostics_callback, show_message_callback=show_message_callback)
        self.output_panel = None
        
    def set_output_panel(self, output_panel) -> None:
        """Set the output panel reference."""
        self.output_panel = output_panel
    
    async def _handle_error(self, log_message: str, panel_message: str = None) -> None:
        """Helper method to handle errors consistently"""
        await self.logger.error(log_message)
        if self.output_panel and panel_message:
            self.output_panel.add_error(panel_message)
    
    async def set_current_model(self, model_id: str) -> None:
        """Set the current AI model for the agent system.
        
        Args:
            model_id: The model identifier (e.g., 'openai', 'claude', etc.)
        """
        try:
            await self.logger.info(f"Setting agent model to: {model_id}")
            self.current_model = model_id
            
            from . import get_agent_context
            agent = await get_agent_context()
            if agent and hasattr(agent, 'set_model'):
                await agent.set_model(model_id)
                
        except Exception as e:
            await self._handle_error(f"Failed to set agent model: {e}", "Failed to set AI model: {e}")
        
    async def initialize(self, progress_callback=None):
        """Initialize the agentic system with progress updates"""
        # Initialize our LSP client first
        await self._initialize_lsp_client(progress_callback)
        
        # Pass our lsp_client to the agentic system
        agent = await initialize_agentic_system(
            str(self.project_root), 
            self.logger, 
            progress_callback, 
            lsp_client=self.lsp_client
        )
        self.agent_initialized = True
        # Store direct references to core components
        if hasattr(agent, 'lsp_indexer'):
            self._lsp_indexer = agent.lsp_indexer
        
    async def _initialize_lsp_client(self, progress_callback=None):
        """Initialize the LSP client for the project"""
        try:
            file_filter = FileFilter(logger=self.logger)
            language = detect_project_language(str(self.project_root))
            
            if language != "unknown":
                config = LanguageConfigs.get_config(language)
                await self.logger.info(f"Starting LSP server for {language}...")
                
                if progress_callback:
                    await progress_callback(f"Starting {language} language server...")
                
                success = await self.lsp_client.start_server(
                    language, 
                    config["command"], 
                    self.project_root
                )
                
                if success:
                    await self.lsp_client.initialize_connection(language, self.project_root, config.get("settings"))
                    await self.logger.info(f"LSP server for {language} started successfully")
                    if progress_callback:
                        await progress_callback(f"{language} language server ready")
                else:
                    await self.logger.warning(f"Failed to start {language} language server")
                    if progress_callback:
                        await progress_callback(f"Failed to start {language} language server")
            else:
                await self.logger.info("No language server configured for this project")
                if progress_callback:
                    await progress_callback("No language server configured")
                    
        except Exception as e:
            await self.logger.warning(f"Failed to initialize LSP client: {e}", exc_info=True)
            if progress_callback:
                await progress_callback(f"LSP initialization error: {e}")
            if self.output_panel:
                self.output_panel.add_error("Language server initialization failed")
            
    @property
    def lsp_indexer(self):
        """Access to the LSP indexer for diagnostics and symbol information"""
        return self._lsp_indexer
    
    async def on_file_open(self, file_path: str):
        """Called when a file is opened in the editor"""
        if not self.agent_initialized:
            return
        
        # Run the context update in a background task to avoid blocking the UI
        asyncio.create_task(self._update_context_background(file_path))

    async def _update_context_background(self, file_path: str):
        """Update agent context in the background"""
        try:
            from . import get_agent_context
            agent = await get_agent_context()
            if agent is None:
                await self.logger.warning(f"Agent context not available for file {file_path}")
                return
                
            await agent.update_context(file_path)
            await self.logger.info(f"Context updated for file: {file_path}")
        except Exception as e:
            await self.logger.warning(f"Failed to update context for file {file_path}: {e}", exc_info=True)
            if self.output_panel:
                self.output_panel.add_error("Failed to update file context")
    
    async def on_file_change(self, file_path: str, old_content: str, new_content: str):
        """Called when file content changes"""
        if not self.agent_initialized:
            return
            
        try:
            await record_code_change(
                file_path=file_path,
                change_type="modify",
                old_content=old_content,
                new_content=new_content
            )
            await self.logger.info(f"Change recorded for file: {file_path}")
        except Exception as e:
            await self.logger.warning(f"Failed to record code change for {file_path}: {e}", exc_info=True)
            if self.output_panel:
                self.output_panel.add_error("Failed to record code changes")
    
    async def on_ai_query(self, query: str, file_path: str = None, 
                         selected_text: str = None, cursor_position: Dict[str, int] = None) -> Dict[str, Any]:
        """Process an AI query with full context"""
        if not self.agent_initialized:
            return {
                "error": "Agentic system not initialized",
                "suggestions": [],
                "related_files": []
            }
        
        try:
            return await process_agent_query(
                query=query,
                file_path=file_path,
                selected_code=selected_text,
                cursor_position=cursor_position
            )
        except Exception as e:
            await self.logger.error(f"Failed to process AI query: {e}", exc_info=True)
            if self.output_panel:
                self.output_panel.add_error("AI query processing failed")
            return {
                "error": str(e),
                "suggestions": [],
                "related_files": []
            }
    
    async def get_file_intelligence(self, file_path: str) -> Dict[str, Any]:
        """Get code intelligence for a specific file"""
        if not self.agent_initialized:
            return {}
            
        try:
            return await get_code_intelligence(file_path)
        except Exception as e:
            await self.logger.warning(f"Failed to get code intelligence for {file_path}: {e}", exc_info=True)
            if self.output_panel:
                self.output_panel.add_error("Code intelligence retrieval failed")
            return {}
    
    async def add_context_file(self, file_path: str, file_content: str = None) -> bool:
        """Add a file to the AI context"""
        if not self.agent_initialized:
            return False
            
        try:
            from . import get_agent_context
            agent = await get_agent_context()
            if agent is None:
                await self.logger.warning(f"Agent context not available for adding file {file_path}")
                return False
                
            return await agent.add_context_file(file_path, file_content)
        except Exception as e:
            await self.logger.warning(f"Failed to add file to context {file_path}: {e}", exc_info=True)
            if self.output_panel:
                self.output_panel.add_error("Failed to add file to AI context")
            return False
    
    async def shutdown(self):
        """Shutdown the agentic system"""
        if self.agent_initialized:
            if self.lsp_client:
                try:
                    for language in list(self.lsp_client.connections.keys()):
                        await self.lsp_client.stop_server(language)
                    await self.logger.info("LSP client shutdown")
                except Exception as e:
                    await self.logger.warning(f"Failed to shutdown LSP client: {e}", exc_info=True)
                    if self.output_panel:
                        self.output_panel.add_error("LSP client shutdown failed")
            
            await shutdown_agentic_system()
            self.agent_initialized = False
            await self.logger.info("Agentic system shutdown")


# Global integration instance
_agent_integration: Optional[K2EditAgentIntegration] = None


async def setup_k2edit_agent(project_root: str = None) -> K2EditAgentIntegration:
    """Setup the K2Edit agent integration"""
    global _agent_integration
    
    if project_root is None:
        project_root = Path.cwd()
    
    _agent_integration = K2EditAgentIntegration(project_root)
    await _agent_integration.initialize()
    
    return _agent_integration


async def get_k2edit_agent() -> Optional[K2EditAgentIntegration]:
    """Get the global agent integration instance"""
    return _agent_integration


# Alias for backward compatibility
AgenticIntegration = K2EditAgentIntegration

