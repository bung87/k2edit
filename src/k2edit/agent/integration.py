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

class K2EditAgentIntegration:
    """Simple integration class for K2Edit agentic system"""
    
    def __init__(self, project_root: str, logger: Logger):
        self.project_root = Path(project_root)
        self.logger = logger
        self.agent_initialized = False
        
    async def initialize(self, progress_callback=None):
        """Initialize the agentic system with progress updates"""
        try:
            await initialize_agentic_system(str(self.project_root), self.logger, progress_callback)
            self.agent_initialized = True
        except Exception as e:
            self.agent_initialized = False
            raise  # Re-raise the exception so main.py can handle it
    
    async def on_file_open(self, file_path: str):
        """Called when a file is opened in the editor"""
        if not self.agent_initialized:
            return
            
        try:
            # Update context with the opened file
            from . import get_agent_context
            agent = await get_agent_context()
            if agent:
                await agent.update_context(file_path)
                await self.logger.info(f"Context updated for file: {file_path}")
        except Exception as e:
            await self.logger.error(f"Error updating context for {file_path}: {e}")
    
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
            await self.logger.error(f"Error recording change for {file_path}: {e}")
    
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
            result = await process_agent_query(
                query=query,
                file_path=file_path,
                selected_code=selected_text,
                cursor_position=cursor_position
            )
            return result
        except Exception as e:
            await self.logger.error(f"Error processing AI query: {e}")
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
            await self.logger.error(f"Error getting code intelligence: {e}")
            return {}
    
    async def add_context_file(self, file_path: str, file_content: str = None) -> bool:
        """Add a file to the AI context"""
        if not self.agent_initialized:
            return False
            
        try:
            from . import get_agent_context
            agent = await get_agent_context()
            if agent:
                return await agent.add_context_file(file_path, file_content)
            return False
        except Exception as e:
            await self.logger.error(f"Error adding file to context: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the agentic system"""
        if self.agent_initialized:
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


# Usage examples for K2Edit integration
class K2EditAppIntegration:
    """Example integration with K2Edit App"""
    
    def __init__(self, app):
        self.app = app
        self.agent = None
    
    async def initialize(self):
        """Initialize agent integration"""
        self.agent = await setup_k2edit_agent()
    
    async def on_file_open(self, file_path):
        """Handle file open event"""
        if self.agent:
            await self.agent.on_file_open(file_path)
    
    async def on_file_change(self, file_path, old_content, new_content):
        """Handle file change event"""
        if self.agent:
            await self.agent.on_file_change(file_path, old_content, new_content)
    
    async def handle_ai_query(self, query):
        """Handle AI query with context"""
        if not self.agent:
            return {"error": "Agent not initialized"}
        
        # Get current file info from app
        current_file = getattr(self.app, 'current_file', None)
        selected_text = getattr(self.app, 'selected_text', None)
        cursor_pos = getattr(self.app, 'cursor_position', None)
        
        return await self.agent.on_ai_query(
            query=query,
            file_path=current_file,
            selected_text=selected_text,
            cursor_position=cursor_pos
        )


# Example usage in K2Edit
if __name__ == "__main__":
    async def demo_integration():
        """Demonstrate K2Edit integration"""
        
        # Initialize
        agent = await setup_k2edit_agent()
        
        # Simulate file open
        await agent.on_file_open("main.py")
        
        # Simulate file change
        old_content = "def old_func():\n    pass"
        new_content = "def new_func():\n    return True"
        await agent.on_file_change("main.py", old_content, new_content)
        
        # Process AI query
        result = await agent.on_ai_query(
            query="suggest improvements for this function",
            file_path="main.py",
            selected_text="def my_function():\n    pass",
            cursor_position={"line": 1, "column": 0}
        )
        
        print("AI Query Result:", result)
        
        # Shutdown
        await agent.shutdown()
    
    asyncio.run(demo_integration())