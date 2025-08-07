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
from textual.widgets import Header, Footer, TextArea
from textual.binding import Binding
from textual.message import Message
from textual.logging import TextualHandler

from .custom_syntax_editor import CustomSyntaxEditor
from .views.command_bar import CommandBar
from .views.output_panel import OutputPanel
from .views.file_explorer import FileExplorer
from .views.status_bar import StatusBar, GitBranchSwitch, NavigateToDiagnostic, ShowDiagnosticsDetails
from .views.modals import DiagnosticsModal, BranchSwitcherModal
from .views.hover_widget import HoverWidget
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
        self.editor = CustomSyntaxEditor(self.logger)
        self.command_bar = CommandBar()
        self.output_panel = OutputPanel(id="output-panel")
        self.file_explorer = FileExplorer(id="file-explorer")
        self.status_bar = StatusBar(id="status-bar", logger=self.logger)
        self.hover_widget = HoverWidget(id="hover-widget")
        self.kimi_api = KimiAPI()
        self.agent_integration = None
        self.initial_file = initial_file
        
        # Hover state
        self._last_cursor_position = (1, 1)  # (line, column)
        self._hover_timer = None
        self._last_hover_content = None
        self._last_hover_position = None


    
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
        
        # Watch for cursor movement
        self.editor.cursor_position_changed = self._on_cursor_position_changed

        # Load initial file if provided, otherwise start with an empty editor
        if self.initial_file:
            file_path = Path(self.initial_file)
            if file_path.is_file():
                await self.logger.info(f"Loading initial file: {self.initial_file}")
                if await self.editor.load_file(self.initial_file):
                    self.output_panel.add_info(f"Loaded file: {self.initial_file}")
                    await self.logger.info(f"Successfully loaded initial file: {self.initial_file}")
                    self.editor.focus()
                    
                    # Update status bar with file information
                    self._update_status_bar()
                    
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
            self.agent_integration = K2EditAgentIntegration(str(Path.cwd()), self.logger, self._on_diagnostics_received)
            
            # Define progress callback to update output panel
            async def progress_callback(message):
                self.output_panel.add_info(message)
                # Don't log here since main.py already logs high-level messages
            
            await self.agent_integration.initialize(progress_callback)
            
            # Update command bar with agent integration
            if hasattr(self, 'command_bar') and self.command_bar:
                self.command_bar.set_agent_integration(self.agent_integration)
            
            # Connect LSP diagnostics to status bar
    
            
            # Add welcome message now that AI system is ready
            self.output_panel.add_welcome_message()
            await self.logger.info("Agentic system initialized successfully")
            
            # Notify LSP server about current file if one is loaded
            if self.editor.current_file:
                current_file_path = str(self.editor.current_file)
                await self.logger.info(f"Notifying LSP server about current file: {current_file_path}")
                await self._on_file_open_with_agent(current_file_path)
        except Exception as e:
            await self.logger.error(f"Failed to initialize agentic system: {e}")
            self.output_panel.add_error(f"Agentic system initialization failed: {e}")
    
    async def _initialize_agent_system(self):
        """Initialize the agentic system asynchronously with progress updates"""
        await self.logger.info("Initializing agentic system...")
        try:
            self.agent_integration = K2EditAgentIntegration(str(Path.cwd()), self.logger, self._on_diagnostics_received)
            
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
            
            # Start language server if not running for this file's language
            if self.agent_integration.lsp_client:
                from .agent.language_configs import LanguageConfigs
                from pathlib import Path
                
                language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
                if language != "unknown" and not self.agent_integration.lsp_client.is_server_running(language):
                    try:
                        await self.logger.info(f"Starting {language} language server for opened file: {file_path}")
                        config = LanguageConfigs.get_config(language)
                        await self.agent_integration.lsp_client.start_server(language, config["command"], str(self.agent_integration.project_root))
                        await self.agent_integration.lsp_client.initialize_connection(language, str(self.agent_integration.project_root))
                        await self.logger.info(f"Started {language} language server successfully")
                    except Exception as e:
                        await self.logger.error(f"Failed to start {language} language server: {e}")
            
            # Notify LSP server about the opened file
            if self.agent_integration.lsp_client:
                await self.agent_integration.lsp_client.notify_file_opened(file_path)
            
        # Diagnostics will be updated automatically via _on_diagnostics_received callback
    
    async def _on_file_change_with_agent(self, file_path: str, old_content: str, new_content: str):
        """Handle file change with agentic system integration"""
        if self.agent_integration:
            await self.agent_integration.on_file_change(file_path, old_content, new_content)
            
            # Notify LSP server about file content changes
            if self.agent_integration.lsp_client:
                await self.agent_integration.lsp_client.notify_file_changed(file_path, new_content)
            

    
    async def _on_diagnostics_received(self, file_path: str, diagnostics: list):
        """Callback for when new diagnostics are received from LSP server"""
        try:
            await self.logger.debug(f"Diagnostics callback triggered for {file_path}: {len(diagnostics)} items")
            
            # Update status bar if this is the current file
            if self.editor.current_file and str(self.editor.current_file) == file_path:
                await self.logger.debug(f"Updating status bar for current file: {file_path}")
                # Format diagnostics data correctly for status bar
                diagnostics_data = {
                    'diagnostics': diagnostics,
                    'file_path': file_path
                }
                self.status_bar.update_diagnostics_from_lsp(diagnostics_data)
            else:
                await self.logger.debug(f"Diagnostics received for non-current file: {file_path}")
        except Exception as e:
            await self.logger.error(f"Error in diagnostics callback: {e}")

    async def _trigger_hover_request(self, line: int, column: int):
        """Trigger LSP hover request after cursor idle."""
        await self.logger.debug(f"_trigger_hover_request: line={line}, column={column}")
        
        if not self.agent_integration or not self.agent_integration.lsp_indexer:
            await self.logger.debug("Hover request skipped: agent integration or lsp_indexer not available")
            return
            
        if not self.editor.current_file:
            await self.logger.debug("Hover request skipped: no current file")
            return
            
        try:
            # Get current file path
            file_path = str(self.editor.current_file)
            await self.logger.debug(f"Requesting hover for: {file_path} at ({line}, {column})")
            
            # Request hover information
            hover_result = await self.agent_integration.lsp_client.get_hover_info(
                file_path, line, column
            )
            await self.logger.debug(f"Hover result: {hover_result is not None}")
            
            if hover_result and "contents" in hover_result:
                # Extract markdown content
                content = self._extract_hover_content(hover_result["contents"])
                await self.logger.debug(f"Extracted hover content length: {len(content) if content else 0}")
                
                if content and content.strip():
                    self._last_hover_content = content
                    await self.logger.debug("Showing hover content")
                    self._show_hover_at_cursor(content)
                else:
                    await self.logger.debug("Hover content empty or invalid")
            else:
                await self.logger.debug("No hover result from LSP")
                    
        except Exception as e:
            await self.logger.error(f"Error in hover request: {e}")

    def _extract_hover_content(self, contents) -> str:
        """Extract markdown content from LSP hover response."""
        if isinstance(contents, str):
            return contents
        elif isinstance(contents, dict):
            # Handle MarkupContent format
            if "value" in contents:
                return contents["value"]
        elif isinstance(contents, list):
            # Handle MarkedString[] format
            content_parts = []
            for item in contents:
                if isinstance(item, str):
                    content_parts.append(item)
                elif isinstance(item, dict) and "value" in item:
                    content_parts.append(item["value"])
            return "\n\n".join(content_parts)
        
        return ""

    def _show_hover_at_cursor(self, content: str) -> None:
        """Show hover content at cursor position in terminal."""
        if not content or not content.strip():
            return
            
        # Get cursor position in terminal coordinates
        line, column = self.editor.cursor_location
        
        # Position hover widget near cursor
        hover_line = line
        hover_column = column
        
        self.hover_widget.show_hover(content, hover_line, hover_column, self.editor)
        self._last_hover_content = content
        self._last_hover_position = (line, column)

    def _on_cursor_position_changed(self, line: int, column: int) -> None:
        """Handle cursor position changes and trigger hover after delay."""
        new_position = (line, column)
        self.logger.debug(f"_on_cursor_position_changed: line={line}, column={column}")
        
        # Hide hover widget on cursor movement
        if self.hover_widget.is_visible():
            self.logger.debug("Hiding hover widget due to cursor movement")
            self.hover_widget.hide_hover()
        
        # Cancel existing hover timer
        if self._hover_timer:
            self.logger.debug("Cancelling existing hover timer")
            self._hover_timer.stop()
            self._hover_timer = None
        
        # Check if position changed
        if new_position == self._last_hover_position and self._last_hover_content:
            # Same position, reuse cached content
            self.logger.debug("Reusing cached hover content for same position")
            self._show_hover_at_cursor(self._last_hover_content)
            return
        
        # Reset cached content for new position
        self._last_hover_content = None
        self._last_hover_position = new_position
        
        # Start new hover timer with 500ms delay
        self.logger.debug("Starting new hover timer with 500ms delay")
        self._hover_timer = self.set_timer(0.5, lambda: asyncio.create_task(self._trigger_hover_request(line, column)))

    async def on_key(self, event) -> None:
        """Handle key presses to dismiss hover."""
        # Dismiss hover on any key press
        if hasattr(self, 'hover_widget') and self.hover_widget.is_visible():
            self.hover_widget.hide_hover()
        
        # Cancel any pending hover request
        if hasattr(self, '_hover_timer') and self._hover_timer is not None:
            self._hover_timer.stop()
            self._hover_timer = None
    
    def compose(self) -> ComposeResult:
        """Create the UI layout with programmatic sizing."""
        with Vertical():
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
            yield self.hover_widget
            yield Footer()  # Removed to avoid conflict with custom status bar

    
    def on_command_bar_command_executed(self, message) -> None:
        """Handle command executed messages from the command bar."""
        self.output_panel.on_command_bar_command_executed(message)
    
    async def on_command_bar_file_opened(self, message) -> None:
        """Handle file opened messages from the command bar."""
        file_path = message.file_path
        await self.logger.info(f"File opened via command: {file_path}")
        
        # Notify agentic system about file open
        await self._on_file_open_with_agent(file_path)

    async def on_file_explorer_file_selected(self, message: FileExplorer.FileSelected) -> None:
        """Handle file selection from the file explorer."""
        file_path = message.file_path
        await self.logger.info(f"File selected from explorer: {file_path}")
        
        if Path(file_path).is_file():
            if await self.editor.load_file(file_path):
                self.output_panel.add_info(f"Loaded file: {file_path}")
                await self.logger.info(f"Successfully loaded file from explorer: {file_path}")
                self.editor.focus()
                
                # Notify agentic system about file open
                await self._on_file_open_with_agent(file_path)
            else:
                error_msg = f"Failed to load file: {file_path}"
                self.output_panel.add_error(error_msg)
                await self.logger.error(error_msg)
        else:
            # It's a directory, keep the tree view
            await self.logger.debug(f"Directory selected: {file_path}")
    
    async def on_text_area_selection_changed(self, event: TextArea.SelectionChanged) -> None:
        """Handle selection/cursor changes in editor."""
        if self.status_bar:
            self.status_bar.update_cursor_position(self.editor.cursor_location[0] + 1, self.editor.cursor_location[1] + 1)

    async def on_text_area_changed(self, event: TextArea.Changed) -> None:
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

    async def on_status_bar_show_diagnostics_details(self, message: ShowDiagnosticsDetails) -> None:
        """Handle show diagnostics details message from status bar."""
        await self.logger.debug("=== DIAGNOSTICS MESSAGE HANDLER TRIGGERED ===")
        await self.logger.debug(f"Showing diagnostics modal with {len(message.diagnostics)} items")
        await self.logger.debug(f"Received ShowDiagnosticsDetails message with {len(message.diagnostics)} diagnostics")
        await self.logger.debug(f"Message type: {type(message)}")
        await self.logger.debug(f"Message sender: {getattr(message, 'sender', 'NO SENDER')}")
        
        try:
            modal = DiagnosticsModal(message.diagnostics, logger=self.logger)
            await self.logger.debug("Created DiagnosticsModal successfully")
            await self.push_screen(modal)
            await self.logger.debug("Pushed DiagnosticsModal to screen")
            await self.logger.debug("=== DIAGNOSTICS MODAL DISPLAYED SUCCESSFULLY ===")
        except Exception as e:
            await self.logger.error(f"Failed to show diagnostics modal: {e}")
            import traceback
            await self.logger.error(traceback.format_exc())

    def show_diagnostics_modal(self, diagnostics: list[Dict[str, Any]]) -> None:
        """Direct method to show diagnostics modal, bypassing message system."""
        self.logger.debug("=== SHOW_DIAGNOSTICS_MODAL CALLED DIRECTLY ===")
        self.logger.debug(f"Diagnostics count: {len(diagnostics)}")
        
        try:
            modal = DiagnosticsModal(diagnostics, logger=self.logger)
            self.logger.debug("Created DiagnosticsModal successfully")
            self.push_screen(modal)
            self.logger.debug("Pushed DiagnosticsModal to screen via direct method")
            self.logger.debug("=== DIAGNOSTICS MODAL DISPLAYED VIA DIRECT CALL ===")
        except Exception as e:
            self.logger.error(f"Failed to show diagnostics modal via direct call: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    async def on_status_bar_git_branch_switch(self, message: GitBranchSwitch) -> None:
        """Handle git branch switch message from status bar."""
        await self.logger.info(f"Switching to git branch: {message.branch_name}")
        
        try:
            import subprocess
            from pathlib import Path
            
            current_dir = Path.cwd()
            
            # Check if we're in a git repository
            git_dir = current_dir / ".git"
            if not git_dir.exists():
                self.output_panel.add_error("Not in a git repository")
                return
            
            # Switch branch
            result = subprocess.run(
                ["git", "checkout", message.branch_name],
                capture_output=True,
                text=True,
                cwd=current_dir,
                timeout=10
            )
            
            if result.returncode == 0:
                self.output_panel.add_info(f"Switched to branch: {message.branch_name}")
                await self.status_bar._update_git_branch()  # Refresh branch display
            else:
                error_msg = f"Failed to switch branch: {result.stderr}"
                self.output_panel.add_error(error_msg)
                await self.logger.error(error_msg)
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            error_msg = f"Error switching branch: {e}"
            self.output_panel.add_error(error_msg)
            await self.logger.error(error_msg)

    async def on_navigate_to_diagnostic(self, message: NavigateToDiagnostic) -> None:
        """Handle navigate to diagnostic message."""
        await self.logger.debug(f"Navigating to diagnostic: {message.file_path}:{message.line}:{message.column}")
        
        try:
            # Open the file if it's not already open
            if message.file_path != str(self.editor.current_file):
                if self.editor.load_file(message.file_path):
                    self.output_panel.add_info(f"Opened file: {message.file_path}")
                    await self.logger.debug(f"Successfully opened file: {message.file_path}")
                else:
                    self.output_panel.add_error(f"Failed to open file: {message.file_path}")
                    await self.logger.error(f"Failed to open file: {message.file_path}")
                    return
            
            # Navigate to the specific line and column
            line_idx = max(0, message.line - 1)
            col_idx = max(0, message.column - 1)
            self.editor.cursor_location = (line_idx, col_idx)
            # self.editor.scroll_to_line(line_idx)
            self.editor.focus()
            
            await self.logger.debug(f"Successfully navigated to line {message.line}, column {message.column}")
            
        except Exception as e:
            error_msg = f"Error navigating to diagnostic: {e}"
            self.output_panel.add_error(error_msg)
            await self.logger.error(error_msg)


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