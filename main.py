#!/usr/bin/env python3
"""
Kimi-K2 Terminal Code Editor
A terminal-based code editor with AI integration using Textual framework.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import asyncio
from typing import Dict, Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer
from textual.binding import Binding
from textual.message import Message
from textual.logging import TextualHandler

from custom_syntax_editor import CustomSyntaxEditor
from views.command_bar import CommandBar
from views.output_panel import OutputPanel
from views.file_explorer import FileExplorer
from agent.kimi_api import KimiAPI
from agent.integration import K2EditAgentIntegration


def setup_logging(log_level: str = "DEBUG") -> logging.Logger:
    """Setup logging configuration with both file and Textual handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"k2edit.log"
    
    # Configure root logger
    logger = logging.getLogger("k2edit")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # File handler for persistent logging <mcreference link="https://docs.python.org/3/library/logging.html" index="1">1</mcreference>
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Textual handler for in-app logging <mcreference link="https://textual.textualize.io/api/logging/" index="3">3</mcreference>
    textual_handler = TextualHandler()
    textual_handler.setLevel(getattr(logging, log_level.upper()))
    textual_handler.setFormatter(console_formatter)
    logger.addHandler(textual_handler)
    
    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    # Set httpx and httpcore loggers to WARNING to avoid excessive INFO logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Set OpenAI client loggers to WARNING to prevent console output in TUI
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("openai._base_client").setLevel(logging.WARNING)
    logging.getLogger("openai.api_requestor").setLevel(logging.WARNING)
    logging.getLogger("openai.api_resources").setLevel(logging.WARNING)
    
    logger.info(f"Logging initialized - Log file: {log_file}")
    return logger


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
    
    def __init__(self, initial_file: str = None, logger: logging.Logger = None, **kwargs):
        super().__init__(**kwargs)
        
        # Setup logging
        self.logger = logger or logging.getLogger("k2edit")
        
        # Initialize components
        self.editor = CustomSyntaxEditor(app_instance=self)
        self.command_bar = CommandBar()
        self.output_panel = OutputPanel(id="output-panel")
        self.file_explorer = FileExplorer(id="file-explorer")
        self.kimi_api = KimiAPI()
        self.agent_integration = None
        self.initial_file = initial_file
        
        self.logger.info("K2EditApp initialized successfully")
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.logger.info("Mounting K2EditApp")
        
        # Connect command bar to other components
        self.command_bar.editor = self.editor
        self.command_bar.output_panel = self.output_panel
        self.command_bar.kimi_api = self.kimi_api
        self.command_bar.set_agent_integration(self.agent_integration)
        
        # Initialize agentic system
        asyncio.create_task(self._initialize_agent_system())
        
        # Listen for file selection messages from file explorer
        self.file_explorer.watch_file_selected = self.on_file_explorer_file_selected

        # Load initial file if provided
        if self.initial_file:
            self.logger.info(f"Loading initial file: {self.initial_file}")
            if Path(self.initial_file).is_file():
                if self.editor.load_file(self.initial_file):
                    self.output_panel.add_info(f"Loaded file: {self.initial_file}")
                    self.logger.info(f"Successfully loaded initial file: {self.initial_file}")
                    self.editor.focus()
                    
                    # Notify agentic system about file open
                    asyncio.create_task(self._on_file_open_with_agent(self.initial_file))
                else:
                    error_msg = f"Failed to load file: {self.initial_file}"
                    self.output_panel.add_error(error_msg)
                    self.logger.error(error_msg)
        
        self.logger.info("K2EditApp mounted successfully")
    
    async def _initialize_agent_system(self):
        """Initialize the agentic system asynchronously"""
        try:
            self.agent_integration = K2EditAgentIntegration(str(Path.cwd()))
            await self.agent_integration.initialize()
            self.output_panel.add_info("Agentic system initialized")
            # Update command bar with agent integration
            if hasattr(self, 'command_bar') and self.command_bar:
                self.command_bar.set_agent_integration(self.agent_integration)
            # Add welcome message now that AI system is ready
            self.output_panel.add_welcome_message()
            self.logger.info("Agentic system initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize agentic system: {e}")
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
        yield Footer()
        
    def on_command_bar_command_executed(self, message) -> None:
        """Handle command executed messages from the command bar."""
        self.output_panel.on_command_bar_command_executed(message)

    def on_file_explorer_file_selected(self, message: FileExplorer.FileSelected) -> None:
        """Handle file selection from the file explorer."""
        file_path = message.file_path
        self.logger.info(f"File selected from explorer: {file_path}")
        
        if Path(file_path).is_file():
            if self.editor.load_file(file_path):
                self.output_panel.add_info(f"Loaded file: {file_path}")
                self.logger.info(f"Successfully loaded file from explorer: {file_path}")
                self.editor.focus()
                
                # Notify agentic system about file open
                asyncio.create_task(self._on_file_open_with_agent(file_path))
            else:
                error_msg = f"Failed to load file: {file_path}"
                self.output_panel.add_error(error_msg)
                self.logger.error(error_msg)
        else:
            # It's a directory, keep the tree view
            self.logger.debug(f"Directory selected: {file_path}")
    
    def on_file_explorer_add_to_context(self, message: FileExplorer.AddToContext) -> None:
        """Handle adding file to AI context from file explorer."""
        file_path = message.file_path
        self.logger.info(f"Adding file to AI context: {file_path}")
        
        if Path(file_path).is_file():
            # Add file to agent context
            asyncio.create_task(self._add_file_to_context(file_path))
            self.output_panel.add_info(f"Added to AI context: {Path(file_path).name}")
        else:
            self.output_panel.add_error(f"Cannot add directory to context: {file_path}")
    
    async def _add_file_to_context(self, file_path: str) -> None:
        """Add file to AI agent context."""
        if not self.agent_integration:
            self.output_panel.add_error("Agentic system not initialized")
            return
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add to agent context via integration
            success = await self.agent_integration.add_context_file(file_path, content)
            if success:
                self.logger.info(f"Successfully added {file_path} to AI context")
            else:
                self.output_panel.add_error("Failed to add file to context")
                
        except Exception as e:
            self.logger.error(f"Error adding file to context: {e}")
            self.output_panel.add_error(f"Failed to add file to context: {e}")
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.logger.info("User initiated quit")
        # Shutdown agentic system
        if self.agent_integration:
            asyncio.create_task(self.agent_integration.shutdown())
        self.exit()
    
    def action_open_file(self) -> None:
        """Focus command bar with open command."""
        self.logger.debug("User triggered open file action")
        self.command_bar.focus()
        self.command_bar.set_text("/open ")
    
    def action_save_file(self) -> None:
        """Focus command bar with save command."""
        self.logger.debug("User triggered save file action")
        self.command_bar.focus()
        self.command_bar.set_text("/save")
    
    def action_focus_command(self) -> None:
        """Focus the command bar."""
        self.logger.debug("Focusing command bar")
        self.command_bar.focus()
    
    def action_focus_editor(self) -> None:
        """Focus the editor."""
        self.logger.debug("Focusing editor")
        self.editor.focus()
    
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


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Setup logging - can be configured via environment variable
    log_level = os.getenv("K2EDIT_LOG_LEVEL", "DEBUG")
    logger = setup_logging(log_level)
    
    logger.info("Starting K2Edit application")
    
    # Check for command line arguments
    initial_file = None
    if len(sys.argv) > 1:
        initial_file = sys.argv[1]
        logger.info(f"Initial file specified: {initial_file}")
        
        # Validate file exists
        if not Path(initial_file).exists():
            error_msg = f"File '{initial_file}' not found."
            logger.error(error_msg)
            print(f"Error: {error_msg}")
            sys.exit(1)
    
    # Create and run the application
    app = K2EditApp(initial_file=initial_file, logger=logger)
    logger.info("Starting application main loop")
    app.run()


if __name__ == "__main__":
    main()