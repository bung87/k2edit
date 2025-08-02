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
        
        try:
            # Initialize components
            self.editor = CustomSyntaxEditor(app_instance=self)
            self.command_bar = CommandBar()
            self.output_panel = OutputPanel()
            self.file_explorer = FileExplorer()
            self.kimi_api = KimiAPI()
            self.initial_file = initial_file
            
            self.logger.info("K2EditApp initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize K2EditApp: {e}", exc_info=True)
            raise
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        try:
            self.logger.info("Mounting K2EditApp")
            
            # Connect command bar to other components
            self.command_bar.editor = self.editor
            self.command_bar.output_panel = self.output_panel
            self.command_bar.kimi_api = self.kimi_api
            
            # Listen for file selection messages from file explorer
            
            # Load initial file if provided
            if self.initial_file:
                self.logger.info(f"Loading initial file: {self.initial_file}")
                if self.editor.load_file(self.initial_file):
                    self.output_panel.add_info(f"Loaded file: {self.initial_file}")
                    self.logger.info(f"Successfully loaded file: {self.initial_file}")
                else:
                    error_msg = f"Failed to load file: {self.initial_file}"
                    self.output_panel.add_error(error_msg)
                    self.logger.error(error_msg)
            
            self.logger.info("K2EditApp mounted successfully")
        except Exception as e:
            self.logger.error(f"Error during app mounting: {e}", exc_info=True)
            self.notify(f"Error during startup: {e}", severity="error")
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        with Horizontal():
            yield self.file_explorer
            with Vertical(id="main-panel"):
                yield self.editor
                yield self.command_bar
            yield self.output_panel
        yield Footer()
    
    def action_quit(self) -> None:
        """Quit the application."""
        try:
            self.logger.info("User initiated quit")
            self.exit()
        except Exception as e:
            self.logger.error(f"Error during quit: {e}", exc_info=True)
            self.exit()  # Force exit even if there's an error
    
    def action_open_file(self) -> None:
        """Focus command bar with open command."""
        try:
            self.logger.debug("User triggered open file action")
            self.command_bar.focus()
            self.command_bar.set_text("/open ")
        except Exception as e:
            self.logger.error(f"Error in open file action: {e}", exc_info=True)
            self.notify("Error opening file dialog", severity="error")
    
    def action_save_file(self) -> None:
        """Focus command bar with save command."""
        try:
            self.logger.debug("User triggered save file action")
            self.command_bar.focus()
            self.command_bar.set_text("/save")
        except Exception as e:
            self.logger.error(f"Error in save file action: {e}", exc_info=True)
            self.notify("Error opening save dialog", severity="error")
    
    def action_focus_command(self) -> None:
        """Focus the command bar."""
        try:
            self.logger.debug("Focusing command bar")
            self.command_bar.focus()
        except Exception as e:
            self.logger.error(f"Error focusing command bar: {e}", exc_info=True)
    
    def action_focus_editor(self) -> None:
        """Focus the editor."""
        try:
            self.logger.debug("Focusing editor")
            self.editor.focus()
        except Exception as e:
            self.logger.error(f"Error focusing editor: {e}", exc_info=True)
    
    def on_file_explorer_file_selected(self, message: FileExplorer.FileSelected) -> None:
        """Handle file selection from the file explorer."""
        try:
            file_path = message.file_path
            self.logger.info(f"File selected from explorer: {file_path}")
            if self.editor.load_file(file_path):
                self.output_panel.add_info(f"Opened file: {file_path}")
                self.editor.focus()
            else:
                self.output_panel.add_error(f"Failed to open file: {file_path}")
        except Exception as e:
            self.logger.error(f"Error handling file selection: {e}", exc_info=True)
            self.notify(f"Error opening file: {e}", severity="error")


def main():
    """Main entry point."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Setup logging - can be configured via environment variable
        log_level = os.getenv("K2EDIT_LOG_LEVEL", "INFO")
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
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user (Ctrl+C)")
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        # Fallback error handling if logger isn't available
        try:
            logger.critical(f"Critical error in main: {e}", exc_info=True)
        except:
            pass
        print(f"Critical error: {e}")
        sys.exit(1)
    finally:
        try:
            logger.info("K2Edit application shutdown complete")
        except Exception as e:
            # Log the error during shutdown, but don't prevent shutdown
            try:
                import logging
                fallback_logger = logging.getLogger("k2edit")
                fallback_logger.warning(f"Error during shutdown logging: {e}")
            except:
                pass


if __name__ == "__main__":
    main()