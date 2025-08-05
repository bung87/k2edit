#!/usr/bin/env python3
"""
Kimi-K2 Terminal Code Editor
A terminal-based code editor with AI integration using Textual framework.
"""


import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import asyncio
from typing import Dict, Any

from aiologger import Logger

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer
from textual.binding import Binding
from textual.message import Message
from textual.logging import TextualHandler

from .custom_syntax_editor import CustomSyntaxEditor
from .views.command_bar import CommandBar
from .views.output_panel import OutputPanel
from .views.file_explorer import FileExplorer
from .views.status_bar import StatusBar
from .agent.kimi_api import KimiAPI
from .agent.integration import K2EditAgentIntegration
from .logger import setup_logging


class K2EditApp(App):
    """Main application class for the Kimi-K2 code editor."""
    
    TITLE = "K2Edit - Kimi-K2 Code Editor"
    CSS_PATH = "styles.css"
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+o", "open_file", "Open"),
        Binding("ctrl+s", "save_file", "Save"),
        Binding("ctrl+k", "focus_command", "Command"),
        Binding("escape", "focus_editor", "Editor"),
    ]
    
    def __init__(self, initial_file: str = None, logger: Logger = None, **kwargs):
        super().__init__(**kwargs)
        
        # Setup logging
        self.logger = logger or Logger(name="k2edit")
        
        # Initialize components
        self.editor = CustomSyntaxEditor(app_instance=self)
        self.command_bar = CommandBar()
        self.output_panel = OutputPanel(id="output-panel")
        self.file_explorer = FileExplorer(id="file-explorer")
        self.status_bar = StatusBar(id="status-bar", logger=self.logger)
        self.kimi_api = KimiAPI()
        self.agent_integration = None
        self.initial_file = initial_file


    
    async def on_mount(self) -> None:
        """Called when the app is mounted."""
        await self.logger.info("K2Edit app mounted")
        
        # # Force update status bar
        # self._update_status_bar()
        
        # # Set up periodic status bar updates
        # self.set_interval(1, self._update_status_bar)
        
        # Initialize agentic system in background after a short delay
        self.set_timer(2.0, lambda: asyncio.create_task(self._initialize_agent_system_background()))
        
        # Connect command bar to other components
        self.command_bar.editor = self.editor
        self.command_bar.output_panel = self.output_panel
        self.command_bar.kimi_api = self.kimi_api
        self.command_bar.set_agent_integration(self.agent_integration)
        
        # Listen for file selection messages from file explorer
        self.file_explorer.watch_file_selected = self.on_file_explorer_file_selected

        # Load initial file if provided, otherwise start with an empty editor
        if self.initial_file:
            file_path = Path(self.initial_file)
            if file_path.is_file():
                await self.logger.info(f"Loading initial file: {self.initial_file}")
                if self.editor.load_file(self.initial_file):
                    self.output_panel.add_info(f"Loaded file: {self.initial_file}")
                    await self.logger.info(f"Successfully loaded initial file: {self.initial_file}")
                    self.editor.focus()
                    
                    # Notify agentic system about file open (when ready)
                    asyncio.create_task(self._on_file_open_with_agent(self.initial_file))
                else:
                    error_msg = f"Failed to load file: {self.initial_file}"
                    self.output_panel.add_error(error_msg)
                    await self.logger.error(error_msg)
            elif file_path.is_dir():
                await self.logger.warning(f"Initial path is a directory, not a file: {self.initial_file}")
                self.output_panel.add_warning(f"Cannot open a directory: {self.initial_file}")
            else:
                # Path doesn't exist, treat as a new file
                await self.logger.info(f"Initial file does not exist, creating new file: {self.initial_file}")
                self.editor.load_file(self.initial_file) # This will create a new buffer
                self.output_panel.add_info(f"New file: {self.initial_file}")
                self.editor.focus()
        else:
            await self.logger.info("No initial file provided, starting with an empty editor.")
            self.editor.focus()
        
        await self.logger.info("K2EditApp mounted successfully")
    
    async def _initialize_agent_system_background(self):
        """Initialize the agentic system in the background with progress updates"""
        await self.logger.info("Initializing agentic system in background...")
        try:
            self.agent_integration = K2EditAgentIntegration(str(Path.cwd()), self.logger)
            
            # Define progress callback to update output panel
            async def progress_callback(message):
                self.output_panel.add_info(message)
                # Don't log here since main.py already logs high-level messages
            
            await self.agent_integration.initialize(progress_callback)
            
            # Update command bar with agent integration
            if hasattr(self, 'command_bar') and self.command_bar:
                self.command_bar.set_agent_integration(self.agent_integration)
            
            # Add welcome message now that AI system is ready
            self.output_panel.add_welcome_message()
            await self.logger.info("Agentic system initialized successfully")
        except Exception as e:
            await self.logger.error(f"Failed to initialize agentic system: {e}")
            self.output_panel.add_error(f"Agentic system initialization failed: {e}")
    
    async def _initialize_agent_system(self):
        """Initialize the agentic system asynchronously with progress updates"""
        await self.logger.info("Initializing agentic system...")
        try:
            self.agent_integration = K2EditAgentIntegration(str(Path.cwd()), self.logger)
            
            # Define progress callback to update output panel
            async def progress_callback(message):
                self.output_panel.add_info(message)
                # Don't log here since main.py already logs high-level messages
            
            await self.agent_integration.initialize(progress_callback)
            
            # Update command bar with agent integration
            if hasattr(self, 'command_bar') and self.command_bar:
                self.command_bar.set_agent_integration(self.agent_integration)
            
            # Add welcome message now that AI system is ready
            self.output_panel.add_welcome_message()
            await self.logger.info("Agentic system initialized successfully")
        except Exception as e:
            await self.logger.error(f"Failed to initialize agentic system: {e}")
            self.output_panel.add_error(f"Agentic system initialization failed: {e}")
    
    async def _on_file_open_with_agent(self, file_path: str):
        """Handle file open with agentic system integration"""
        if self.agent_integration:
            await self.agent_integration.on_file_open(file_path)
    
    async def _on_file_change_with_agent(self, file_path: str, old_content: str, new_content: str):
        """Handle file change with agentic system integration"""
        if self.agent_integration:
            await self.agent_integration.on_file_change(file_path, old_content, new_content)
    
    def compose(self) -> ComposeResult:
        """Create the UI layout with programmatic sizing."""
        yield Header()
        with Horizontal():
            # File explorer with fixed width
            self.file_explorer.styles.width = "25%"
            self.file_explorer.styles.min_width = "25%"
            self.file_explorer.styles.max_width = "25%"
            yield self.file_explorer
            
            # Main editor panel with explicit width
            with Vertical(id="main-panel") as main_panel:
                main_panel.styles.width = "50%"
                main_panel.styles.min_width = "50%"
                main_panel.styles.max_width = "50%"
                
                self.editor.styles.height = "1fr"
                self.editor.styles.width = "100%"
                self.editor.styles.overflow_x = "hidden"
                self.editor.styles.overflow_y = "auto"
                yield self.editor
                
                self.command_bar.styles.height = 3
                self.command_bar.styles.min_height = 3
                self.command_bar.styles.max_height = 3
                self.command_bar.styles.width = "100%"
                yield self.command_bar
            
            # Output panel with fixed width
            self.output_panel.styles.width = "25%"
            self.output_panel.styles.min_width = "25%"
            self.output_panel.styles.max_width = "25%"
            yield self.output_panel
        # yield self.status_bar
        yield self.status_bar
        # yield Footer()  # Removed to avoid conflict with custom status bar

    
    def on_command_bar_command_executed(self, message) -> None:
        """Handle command executed messages from the command bar."""
        self.output_panel.on_command_bar_command_executed(message)

    async def on_file_explorer_file_selected(self, message: FileExplorer.FileSelected) -> None:
        """Handle file selection from the file explorer."""
        file_path = message.file_path
        await self.logger.info(f"File selected from explorer: {file_path}")
        
        if Path(file_path).is_file():
            if self.editor.load_file(file_path):
                self.output_panel.add_info(f"Loaded file: {file_path}")
                await self.logger.info(f"Successfully loaded file from explorer: {file_path}")
                self.editor.focus()
                
                # Update status bar
                self._update_status_bar()
                
                # Notify agentic system about file open
                await self._on_file_open_with_agent(file_path)
            else:
                error_msg = f"Failed to load file: {file_path}"
                self.output_panel.add_error(error_msg)
                await self.logger.error(error_msg)
        else:
            # It's a directory, keep the tree view
            await self.logger.debug(f"Directory selected: {file_path}")
    
    async def on_text_area_cursor_moved(self, event: CustomSyntaxEditor.CursorMoved) -> None:
        """Handle cursor movement in editor."""
        if self.status_bar:
            self.status_bar.update_cursor_position(event.cursor_location[0] + 1, event.cursor_location[1] + 1)

    async def on_text_area_changed(self, event: CustomSyntaxEditor.Changed) -> None:
        """Handle text changes in editor."""
        if self.status_bar:
            self.status_bar.update_from_editor(self.editor.text, str(self.editor.current_file) if self.editor.current_file else "")

    async def on_file_explorer_add_to_context(self, message: FileExplorer.AddToContext) -> None:
        """Handle adding file to AI context from file explorer."""
        file_path = message.file_path
        await self.logger.info(f"Adding file to AI context: {file_path}")
        
        if Path(file_path).is_file():
            # Add file to agent context
            await self._add_file_to_context(file_path)
            self.output_panel.add_info(f"Added to AI context: {Path(file_path).name}")
        else:
            error_msg = f"Cannot add directory to context: {file_path}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
    
    def on_editor_cursor_moved(self, event) -> None:
        """Handle editor cursor movement."""
        self._update_status_bar()
    
    def on_editor_content_changed(self, event) -> None:
        """Handle editor content changes."""
        self._update_status_bar()
    
    async def _add_file_to_context(self, file_path: str) -> None:
        """Add file to AI agent context."""
        if not self.agent_integration:
            error_msg = "Agentic system not initialized"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add to agent context via integration
            success = await self.agent_integration.add_context_file(file_path, content)
            if success:
                await self.logger.info(f"Successfully added {file_path} to AI context")
            else:
                error_msg = "Failed to add file to context"
                await self.logger.error(error_msg)
                self.output_panel.add_error(error_msg)
                
        except Exception as e:
            await self.logger.error(f"Error adding file to context: {e}")
            self.output_panel.add_error(f"Failed to add file to context: {e}")
    
    async def action_quit(self) -> None:
        """Quit the application."""
        await self.logger.info("User initiated quit")
        # Shutdown agentic system
        if self.agent_integration:
            await self.agent_integration.shutdown()
        self.exit()
    
    async def action_open_file(self) -> None:
        """Focus command bar with open command."""
        await self.logger.debug("User triggered open file action")
        self.command_bar.focus()
        self.command_bar.set_text("/open ")
    
    async def action_save_file(self) -> None:
        """Focus command bar with save command."""
        await self.logger.debug("User triggered save file action")
        self.command_bar.focus()
        self.command_bar.set_text("/save")
    
    async def action_focus_command(self) -> None:
        """Focus the command bar."""
        await self.logger.debug("Focusing command bar")
        self.command_bar.focus()
    
    async def action_focus_editor(self) -> None:
        """Focus the editor."""
        self.editor.focus()
    
    def _update_status_bar(self):
        """Update status bar with current editor information."""
        if self.editor and self.status_bar:
            # Update cursor position
            cursor_location = self.editor.cursor_location
            if cursor_location:
                self.status_bar.update_cursor_position(
                    cursor_location[0] + 1,  # Convert to 1-based
                    cursor_location[1] + 1
                )
            
            # Update file information
            current_file = str(self.editor.current_file) if self.editor.current_file else ""
            file_name = os.path.basename(current_file) if current_file else "New File"
            editor_content = self.editor.text
            
            # Update status bar with editor content and file path
            self.status_bar.update_from_editor(editor_content, current_file)
            
            # Force refresh of status bar
            self.status_bar.refresh()
    
    async def process_agent_query(self, query: str) -> dict[str, any]:
        """Process an AI query using the agentic system"""
        if not self.agent_integration:
            return {"error": "Agentic system not initialized"}
        
        current_file = str(self.editor.current_file) if self.editor.current_file else None
        selected_text = self.editor.get_selected_text() if hasattr(self.editor, 'get_selected_text') else None
        cursor_pos = {"line": self.editor.cursor_line, "column": self.editor.cursor_column}
        
        result = await self.agent_integration.on_ai_query(
            query=query,
            file_path=current_file,
            selected_text=selected_text,
            cursor_position=cursor_pos
        )
        
        return result
    
    async def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        await self.logger.info("Shutting down K2EditApp")
        if self.agent_integration:
            await self.agent_integration.shutdown()
        await self.logger.shutdown()


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Setup logging - can be configured via environment variable
    log_level = os.getenv("K2EDIT_LOG_LEVEL", "DEBUG")
    logger = setup_logging(log_level)

    # Check for command line arguments
    initial_file = None
    
    if len(sys.argv) > 1:
        initial_file = sys.argv[1]

    # Create and run the application
    app = K2EditApp(initial_file=initial_file, logger=logger)
    app.run()


if __name__ == "__main__":
    main()