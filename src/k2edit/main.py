#!/usr/bin/env python3
"""
Kimi-K2 Terminal Code Editor
A terminal-based code editor with AI integration using Textual framework.
"""


import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from typing import Dict, Any

# Performance optimization: Use uvloop for better async performance on Unix systems
try:
    import uvloop
    if sys.platform != "win32":
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    # uvloop not available, continue with default event loop
    pass

from aiologger import Logger

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, TextArea
from textual.widgets._text_area import Selection
from textual.binding import Binding
from textual.message import Message
from textual.logging import TextualHandler
from textual.command import Provider, Hit, Hits

from .custom_syntax_editor import CustomSyntaxEditor
from .views.command_bar import CommandBar
from .views.output_panel import OutputPanel
from .views.file_explorer import FileExplorer
from .views.status_bar import StatusBar, GitBranchSwitch, NavigateToDiagnostic, ShowDiagnosticsDetails
from .views.modals import DiagnosticsModal, BranchSwitcherModal
from .views.settings_modal import SettingsModal
from .views.hover_widget import HoverWidget
from .views.file_path_display import FilePathDisplay
from .views.terminal_panel import TerminalPanel
from .views.search_replace_dialog import SearchReplaceDialog, FindInFilesDialog
from .views.ai_mode_selector import AIModeSelector
from .views.ai_model_selector import AIModelSelector
from .utils.search_manager import SearchManager
from .agent.kimi_api import KimiAPI
from .agent.integration import K2EditAgentIntegration
from .logger import setup_logging
from .utils import (
    get_config
)
from .utils.initialization import (
    create_agent_initializer,
    AgentInitializer,
)
from .utils.async_performance_utils import (
    get_performance_monitor,
    get_task_queue,
    OptimizedThreadPoolExecutor
)


class K2EditCommands(Provider):
    """Command provider for K2Edit editor features."""
    
    async def search(self, query: str) -> Hits:
        """Search for available commands."""
        matcher = self.matcher(query)
        
        commands = [
            # File operations
            ("open", "Open file", lambda: self.app.action_open_file()),
            ("save", "Save current file", lambda: self.app.action_save_file()),
            ("quit", "Quit application", lambda: self.app.action_quit()),
            
            # Search & Replace
            ("find", "Find text", lambda: self.app.action_show_find()),
            ("replace", "Replace text", lambda: self.app.action_show_replace()),
            ("find in files", "Find in files", lambda: self.app.action_find_in_files()),
            ("find next", "Find next occurrence", lambda: self.app.action_find_next()),
            ("find previous", "Find previous occurrence", lambda: self.app.action_find_previous()),
            ("replace all", "Replace all occurrences", lambda: self.app.action_replace_all()),
            
            # View & Layout
            ("toggle sidebar", "Toggle sidebar visibility", lambda: self.app.action_toggle_sidebar()),
            ("toggle terminal", "Toggle terminal panel", lambda: self.app.action_toggle_terminal()),
            ("toggle fullscreen", "Toggle fullscreen mode", lambda: self.app.action_toggle_fullscreen()),
            ("zoom in", "Zoom in", lambda: self.app.action_zoom_in()),
            ("zoom out", "Zoom out", lambda: self.app.action_zoom_out()),
            
            # Advanced features
            ("run file", "Run current file", lambda: self.app.action_run_current_file()),
            ("format code", "Format current code", lambda: self.app.action_format_code()),
            
            # Focus
            ("focus command", "Focus command bar", lambda: self.app.action_focus_command()),
            ("focus editor", "Focus editor", lambda: self.app.action_focus_editor()),
            
            # Settings
            ("settings", "Open AI model settings", lambda: self.app.action_show_settings()),
        ]
        
        for name, description, callback in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=description
                )


class K2EditApp(App):
    """Main application class for the Kimi-K2 code editor."""
    
    TITLE = "K2Edit - Kimi-K2 Code Editor"
    CSS_PATH = "styles.tcss"
    COMMANDS = App.COMMANDS | {K2EditCommands}
    
    BINDINGS = [
        # File operations
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+o", "open_file", "Open"),
        Binding("ctrl+s", "save_file", "Save"),
        Binding("ctrl+k", "focus_command", "Command"),
        Binding("escape", "focus_editor", "Editor"),
        
        # Search & Replace
        Binding("ctrl+f", "show_find", "Find"),
        Binding("f3", "find_next", "Find Next"),
        Binding("shift+f3", "find_previous", "Find Previous"),
        Binding("ctrl+h", "show_replace", "Replace"),
        Binding("ctrl+shift+h", "replace_all", "Replace All"),
        Binding("ctrl+shift+f", "find_in_files", "Find in Files"),
        
        # View & Layout
        Binding("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        Binding("ctrl+grave_accent", "toggle_terminal", "Terminal"),
        Binding("f11", "toggle_fullscreen", "Fullscreen"),
        
        # Zoom
        Binding("ctrl+plus", "zoom_in", "Zoom In"),
        Binding("ctrl+minus", "zoom_out", "Zoom Out"),
        Binding("ctrl+equal", "zoom_in", "Zoom In"),  # Alternative for +
        Binding("ctrl+underscore", "zoom_out", "Zoom Out"),  # Alternative for -
        
        # Advanced
        Binding("f5", "run_current_file", "Run File"),
        Binding("ctrl+f5", "run_current_file", "Run File"),
        Binding("ctrl+shift+i", "format_code", "Format Code"),
        
        # Settings
        Binding("ctrl+comma", "show_settings", "Settings"),
    ]
    
    def __init__(self, initial_file: str = None, logger: Logger = None, **kwargs):
        super().__init__(**kwargs)
        
        # Setup logging and configuration
        self.logger = logger or Logger(name="k2edit")
        self.config = get_config()
        

        # Initialize components
        self.editor = CustomSyntaxEditor(self.logger)
        self.command_bar = CommandBar()
        self.output_panel = OutputPanel(id="output-panel")
        self.ai_mode_selector = AIModeSelector(id="ai-mode-selector")
        self.ai_model_selector = AIModelSelector(logger=self.logger, id="ai-model-selector")
        self.file_explorer = FileExplorer(id="file-explorer", logger=self.logger)
        self.status_bar = StatusBar(id="status-bar", logger=self.logger)
        self.hover_widget = HoverWidget(id="hover-widget", logger=self.logger)
        self.file_path_display = FilePathDisplay(id="file-path-display")
        self.terminal_panel = TerminalPanel(id="terminal-panel", logger=self.logger)
        self.kimi_api = KimiAPI(self.logger)
        self.agent_integration = None
        self.initial_file = initial_file
        
        # Search and UI state
        self.search_manager = SearchManager(self.logger)
        self.sidebar_visible = True
        self.fullscreen_mode = False
        self.zoom_level = 1.0
        self.current_search_dialog = None
        self.current_ai_mode = "ask"  # Default AI mode
        
        # Set up go-to-definition navigation callback
        self.editor.set_goto_definition_callback(self._navigate_to_definition)
        
        # Initialize utility classes
        self.agent_initializer = create_agent_initializer(self.logger)
        
        # Performance monitoring and async utilities
        self.performance_monitor = get_performance_monitor(self.logger)
        self.thread_pool = OptimizedThreadPoolExecutor()
        
        # Initialize task queue for async operations
        self._task_queue = None
        
        # Hover state
        self._last_cursor_position = (1, 1)  # (line, column)
        self._hover_timer = None
        self._last_hover_content = None
        self._last_hover_position = None


    
    async def on_mount(self) -> None:
        """Called when the app is mounted."""
        await self.logger.info("K2Edit app mounted")
        
        # Initialize task queue
        self._task_queue = await get_task_queue()
        
        # Determine project root based on initial file/directory
        self.project_root = self._determine_project_root()
        self.file_path_display.set_project_root(self.project_root)
        
        # Initialize agentic system in background using task queue
        await self._task_queue.submit_task(self._initialize_agent_system, priority=1)
        
        # Connect command bar to other components
        self.command_bar.editor = self.editor
        self.command_bar.output_panel = self.output_panel
        self.command_bar.kimi_api = self.kimi_api
        self.command_bar.set_agent_integration(self.agent_integration)
        self.command_bar.set_output_panel(self.output_panel)
        
        # Listen for file selection messages from file explorer
        self.file_explorer.watch_file_selected = self.on_file_explorer_file_selected
        
        # Watch for cursor movement using task queue
        self.editor.cursor_position_changed = lambda line, column: asyncio.create_task(
            self._task_queue.submit_task(self._on_cursor_position_changed, line, column, priority=3)
        ) if self._task_queue else None

        # Load initial file if provided, otherwise start with an empty editor
        if self.initial_file:
            await self.open_path(self.initial_file)
        else:
            await self.logger.info("No initial file provided, starting with an empty editor.")
            self.file_path_display.set_file(None)
            self.editor.focus()
        
        await self.logger.info("K2EditApp mounted successfully")
    
    async def _on_show_message_received(self, message_type: int, language: str, message: str) -> None:
        """Handle LSP show messages by displaying them as notifications."""
        try:
            # Map LSP message types to textual notification severities
            if message_type == 1:  # Error
                self.notify(message, severity="error", title=f"{language.upper()} LSP")
            elif message_type == 2:  # Warning
                self.notify(message, severity="warning", title=f"{language.upper()} LSP")
            else:  # Info (3) or Log (4)
                self.notify(message, severity="information", title=f"{language.upper()} LSP")
        except Exception as e:
            await self.logger.error(f"Error handling show message: {e}")
    
    def _determine_project_root(self) -> str:
        """Determine the project root based on initial file/directory parameter.
        
        Returns:
            str: The project root directory path
        """
        if self.initial_file:
            initial_path = Path(self.initial_file)
            if initial_path.is_dir():
                # If initial file is a directory, use it as project root
                return str(initial_path.resolve())
            elif initial_path.exists():
                # If initial file is a file, use its parent directory as project root
                return str(initial_path.parent.resolve())
            else:
                # If initial file doesn't exist, try to use its parent directory
                return str(initial_path.parent.resolve())
        else:
            # No initial file provided, use current working directory
            return str(Path.cwd())
    
    async def _initialize_agent_system(self):
        """Initialize the agentic system using the standardized initializer with performance monitoring."""
        # Start performance monitoring
        self.performance_monitor.start_timer("agent_initialization")
        
        # Define progress callback to update output panel
        async def progress_callback(message):
            self.output_panel.add_info(message)
        
        # Get current file if available
        current_file = str(self.editor.current_file) if self.editor.current_file else None
        
        try:
            # Initialize agent system with performance monitoring
            self.agent_integration = await self.agent_initializer.initialize_agent_system(
                project_root=self.project_root,
                diagnostics_callback=self._on_diagnostics_received,
                show_message_callback=self._on_show_message_received,
                progress_callback=progress_callback,
                command_bar=self.command_bar,
                output_panel=self.output_panel,
                current_file=current_file
            )
        finally:
            # Log initialization time
            init_time = self.performance_monitor.end_timer("agent_initialization")
            await self.logger.info(f"Agent system initialization completed in {init_time:.2f}s")
        
        # Set output panel for agent integration error handling
        if self.agent_integration:
            self.agent_integration.set_output_panel(self.output_panel)
            
            # Update project root for file path display
            self.file_path_display.set_project_root(str(self.agent_integration.project_root))
            
            # Set up LSP client for go-to-definition
            if self.agent_integration.lsp_client and self.agent_integration.lsp_client.connections:
                await self.logger.debug(f"LSP client has {len(self.agent_integration.lsp_client.connections)} active connections, setting up editor and updating status to Connected")
                self.editor.set_lsp_client(self.agent_integration.lsp_client)
                self.status_bar.update_language_server_status("Connected")
                await self.logger.debug("LSP status updated to Connected")
            else:
                await self.logger.debug("No LSP client connections available, updating status to Disconnected")
                self.status_bar.update_language_server_status("Disconnected")
                await self.logger.debug("LSP status updated to Disconnected")
    
    async def open_path(self, file_path: str) -> bool:
        """Open a file or directory path, handling both scenarios appropriately.
        
        Args:
            file_path: Path to the file or directory to open
            
        Returns:
            bool: True if path was successfully opened, False otherwise
        """
        # Validate path format first
        try:
            from .utils.path_validation import validate_file_path, validate_directory_path
        except ImportError as e:
            error_msg = f"Failed to import path validation utilities: {e}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return False
        
        # Check if path exists and determine type
        try:
            path = Path(file_path)
            if not path.exists():
                # For non-existent paths, try file validation with allow_create
                try:
                    is_valid, error_msg = validate_file_path(file_path, allow_create=True)
                    if not is_valid:
                        self.output_panel.add_error(error_msg)
                        await self.logger.error(error_msg)
                        return False
                except (ValueError, TypeError) as e:
                    error_msg = f"Invalid file path format: {file_path}"
                    await self.logger.error(error_msg)
                    self.output_panel.add_error(error_msg)
                    return False
                return await self._open_file_internal(file_path)
            
            # Handle directory case
            if path.is_dir():
                return await self.open_directory(file_path)
            
            # Handle file case - validate as file
            try:
                is_valid, error_msg = validate_file_path(file_path, allow_create=True)
                if not is_valid:
                    self.output_panel.add_error(error_msg)
                    await self.logger.error(error_msg)
                    return False
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid file path format: {file_path}"
                await self.logger.error(error_msg)
                self.output_panel.add_error(error_msg)
                return False
                
            return await self._open_file_internal(file_path)
            
        except FileNotFoundError:
            error_msg = f"File not found: {file_path}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return False
        except PermissionError:
            error_msg = f"Permission denied accessing: {file_path}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return False
        except OSError as e:
            error_msg = f"OS error opening {file_path}: {e}"
            await self.logger.error(error_msg, exc_info=True)
            self.output_panel.add_error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected error opening {file_path}: {e}"
            await self.logger.error(error_msg, exc_info=True)
            self.output_panel.add_error(error_msg)
            return False
    
    async def open_directory(self, directory_path: str) -> bool:
        """Handle directory opening by setting it as file explorer root.
        
        Args:
            directory_path: Path to the directory to open
            
        Returns:
            bool: True if directory was successfully set as root, False otherwise
        """
        # Import validation utilities
        try:
            from .utils.path_validation import validate_directory_path
        except ImportError as e:
            error_msg = f"Failed to import path validation utilities: {e}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return False
        
        # Validate directory path
        try:
            is_valid, error_msg = validate_directory_path(directory_path)
            if not is_valid:
                self.output_panel.add_error(error_msg)
                await self.logger.error(error_msg)
                return False
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid directory path format: {directory_path}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return False
        
        # Set as file explorer root
        try:
            await self.logger.info(f"Setting directory as file explorer root: {directory_path}")
            await self.file_explorer.set_root_path(Path(directory_path))
            
            # Update file path display to show directory
            self.file_path_display.set_project_root(directory_path)
            
            return True
            
        except FileNotFoundError:
            error_msg = f"Directory not found: {directory_path}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return False
        except PermissionError:
            error_msg = f"Permission denied accessing directory: {directory_path}"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return False
        except OSError as e:
            error_msg = f"OS error opening directory {directory_path}: {e}"
            await self.logger.error(error_msg, exc_info=True)
            self.output_panel.add_error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected error opening directory {directory_path}: {e}"
            await self.logger.error(error_msg, exc_info=True)
            self.output_panel.add_error(error_msg)
            return False
    
    async def _open_file_internal(self, file_path: str) -> bool:
        """Internal method to handle actual file opening.
        
        Args:
            file_path: Path to the file to open
            
        Returns:
            bool: True if file was successfully opened, False otherwise
        """
        # Load the file into the editor
        success = await self.editor.load_file(file_path)
        if not success:
            error_msg = f"Failed to load file: {file_path}"
            self.output_panel.add_error(error_msg)
            await self.logger.error(error_msg)
            return False
        
        # Update UI components
        self.output_panel.add_info(f"Loaded file: {file_path}")
        await self.logger.info(f"Successfully loaded file: {file_path}")
        self.editor.focus()
        
        # Update file path display
        self.file_path_display.set_file(file_path)
        
        # Update status bar
        await self._update_status_bar()
        
        # Notify agentic system about file open
        await self._on_file_open_with_agent(file_path)
        
        return True
    
    async def _on_file_open_with_agent(self, file_path: str):
        """Handle file open with agentic system integration"""
        if self.agent_integration:
            await self.agent_integration.on_file_open(file_path)
            
            # Start language server if not running for this file's language
            if self.agent_integration.lsp_client:
                from .agent.language_configs import LanguageConfigs
                from pathlib import Path
                from .utils.language_utils import detect_language_by_extension
                
                language = detect_language_by_extension(Path(file_path).suffix)
                if language != "unknown" and not self.agent_integration.lsp_client.is_server_running(language):
                    try:
                        await self.logger.info(f"Starting {language} language server for file: {file_path}")
                        config = LanguageConfigs.get_config(language)
                        # Start server initialization in background to avoid blocking UI
                        asyncio.create_task(self._start_language_server_async(language, config, file_path))
                        # Update LSP status immediately to show "Starting" state
                        await self._update_lsp_status()
                    except KeyError as e:
                        await self.logger.error(f"Language server configuration not found for {language}: {e}")
                        await self._update_lsp_status()
                    except FileNotFoundError:
                        await self.logger.error(f"Language server executable not found for {language}")
                        await self._update_lsp_status()
                    except ConnectionError as e:
                        await self.logger.error(f"Failed to connect to {language} language server: {e}")
                        await self._update_lsp_status()
                    except TimeoutError:
                        await self.logger.error(f"Timeout starting {language} language server")
                        await self._update_lsp_status()
                    except Exception as e:
                        await self.logger.error(f"Unexpected error starting {language} language server: {e}", exc_info=True)
                        await self._update_lsp_status()
            
            # Notify LSP server about the opened file
            if self.agent_integration.lsp_client:
                await self.agent_integration.lsp_client.notify_file_opened(file_path)
    
    async def _start_language_server_async(self, language: str, config: dict, file_path: str):
        """Start language server asynchronously without blocking UI"""
        try:
            # Start the server
            success = await self.agent_integration.lsp_client.start_server(
                language, config["command"], str(self.agent_integration.project_root)
            )
            
            if success:
                # Initialize connection
                init_success = await self.agent_integration.lsp_client.initialize_connection(
                    language, str(self.agent_integration.project_root)
                )
                
                if init_success:
                    await self.logger.info(f"Started {language} language server successfully")
                else:
                    await self.logger.error(f"Failed to initialize {language} language server connection")
            else:
                await self.logger.error(f"Failed to start {language} language server")
                
        except Exception as e:
            await self.logger.error(f"Error in background language server startup for {language}: {e}", exc_info=True)
        finally:
            # Always update LSP status after completion
            await self._update_lsp_status()

    
    async def _update_lsp_status(self):
        """Update LSP status bar based on current connection state"""
        if not self.agent_integration or not self.agent_integration.lsp_client:
            await self.logger.debug("Updating LSP status to Disconnected - no agent integration or LSP client")
            self.status_bar.update_language_server_status("Disconnected")
            return
            
        # Check if there are any active connections
        active_connections = [
            lang for lang, conn in self.agent_integration.lsp_client.connections.items()
            if conn.is_healthy()
        ]
        
        if active_connections:
            status = f"Connected ({', '.join(active_connections)})"
            await self.logger.debug(f"Updating LSP status to {status}")
            self.status_bar.update_language_server_status("Connected")
        else:
            await self.logger.debug("Updating LSP status to Disconnected - no active connections")
            self.status_bar.update_language_server_status("Disconnected")
    
    async def _on_file_change_with_agent(self, file_path: str, old_content: str, new_content: str):
        """Handle file change with agentic system integration"""
        if self.agent_integration:
            await self.agent_integration.on_file_change(file_path, old_content, new_content)
            
            # Notify LSP server about file content changes
            if self.agent_integration.lsp_client:
                await self.agent_integration.lsp_client.notify_file_changed(file_path, new_content)
            

    
    async def _on_diagnostics_received(self, file_path: str, diagnostics: list):
        """Callback for when new diagnostics are received from LSP server"""
        if not diagnostics or not isinstance(diagnostics, list):
            await self.logger.debug(f"Invalid or empty diagnostics for {file_path}")
            return
            
        try:
            await self.logger.debug(f"Diagnostics callback triggered for {file_path}: {len(diagnostics)} items")
            
            # Always update status bar with diagnostics, regardless of current file
            await self.logger.debug(f"Updating status bar with diagnostics for: {file_path}")
            # Format diagnostics data correctly for status bar
            diagnostics_data = {
                'diagnostics': diagnostics,
                'file_path': file_path
            }
            await self.status_bar.update_diagnostics_from_lsp(diagnostics_data)
            
            if self.editor.current_file and str(self.editor.current_file) == file_path:
                await self.logger.debug(f"Diagnostics updated for current file: {file_path}")
            else:
                await self.logger.debug(f"Diagnostics updated for non-current file: {file_path}")
        except AttributeError as e:
            await self.logger.error(f"Status bar method not available: {e}")
            self.output_panel.add_error("Failed to update diagnostics display")
        except KeyError as e:
            await self.logger.error(f"Missing required diagnostics data: {e}")
            self.output_panel.add_error("Invalid diagnostics data format")
        except Exception as e:
            await self.logger.error(f"Unexpected error processing diagnostics for {file_path}: {e}", exc_info=True)
            self.output_panel.add_error("Failed to process diagnostics")

    async def _trigger_hover_request(self, line: int, column: int):
        """Trigger LSP hover request after cursor idle."""

        if not self.agent_integration or not self.agent_integration.lsp_indexer:
            await self.logger.debug("Hover request skipped: agent integration or lsp_indexer not available")
            return
            
        if not self.editor.current_file:
            await self.logger.debug("Hover request skipped: no current file")
            return
            
        # Get current file path
        try:
            file_path = str(self.editor.current_file)
        except AttributeError as e:
            await self.logger.error(f"Editor current_file not available: {e}")
            return
            
        await self.logger.debug(f"Requesting hover for: {file_path} at ({line}, {column})")
        
        # Request hover information from LSP
        try:
            hover_result = await self.agent_integration.lsp_client.get_hover_info(
                file_path, line, column
            )
        except AttributeError as e:
            await self.logger.error(f"LSP client method not available: {e}")
            return
        except ConnectionError as e:
            await self.logger.error(f"LSP connection error during hover request: {e}")
            return
        except ValueError as e:
            await self.logger.error(f"Invalid hover request parameters: {e}")
            return
            
        await self.logger.debug(f"Hover result: {hover_result is not None}")
        
        if hover_result and "contents" in hover_result:
            # Extract markdown content
            try:
                content = self._extract_hover_content(hover_result["contents"])
            except KeyError as e:
                await self.logger.error(f"Missing expected data in hover response: {e}")
                return
                
            await self.logger.debug(f"Extracted hover content length: {len(content) if content else 0}")
            
            if content and content.strip():
                self._last_hover_content = content
                await self._show_hover_at_cursor(content)
            else:
                await self.logger.debug("Hover content empty or invalid")
        else:
            await self.logger.debug("No hover result from LSP")

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

    async def _show_hover_at_cursor(self, content: str) -> None:
        """Show hover content at cursor position in terminal."""
        if not content or not content.strip():
            return
            
        # Get cursor position in terminal coordinates with safe unpacking
        try:
            cursor_location = self.editor.cursor_location
            if isinstance(cursor_location, (tuple, list)) and len(cursor_location) >= 2:
                line, column = cursor_location[0], cursor_location[1]
            else:
                await self.logger.error(f"Invalid cursor_location format: {cursor_location}")
                return
        except Exception as e:
            await self.logger.error(f"Error getting cursor location: {e}")
            return
        
        # Position hover widget near cursor
        hover_line = line
        hover_column = column
        
        await self.hover_widget.show_hover(content, hover_line, hover_column, self.editor)
        self._last_hover_content = content
        self._last_hover_position = (line, column)

    async def _on_cursor_position_changed(self, line: int, column: int) -> None:
        """Handle cursor position changes and trigger hover after delay."""
        new_position = (line, column)
        
        # Hide hover widget on cursor movement
        if self.hover_widget.is_visible():
            await self.logger.debug("Hiding hover widget due to cursor movement")
            await self.hover_widget.hide_hover()
        
        # Cancel existing hover timer
        if self._hover_timer:
            await self.logger.debug("Cancelling existing hover timer")
            self._hover_timer.stop()
            self._hover_timer = None
        
        # Check if position changed
        if new_position == self._last_hover_position and self._last_hover_content:
            # Same position, reuse cached content
            await self.logger.debug("Reusing cached hover content for same position")
            await self._show_hover_at_cursor(self._last_hover_content)
            return
        
        # Reset cached content for new position
        self._last_hover_content = None
        self._last_hover_position = new_position
        
        # Start new hover timer with 500ms delay
        await self.logger.debug("Starting new hover timer with 500ms delay")
        self._hover_timer = self.set_timer(0.5, lambda: asyncio.create_task(
            self._task_queue.submit_task(self._trigger_hover_request, line, column, priority=4)
        ) if self._task_queue else asyncio.create_task(self._trigger_hover_request(line, column)))

    async def _navigate_to_definition(self, definitions: list[dict[str, Any]]) -> None:
        """Navigate to the definition location(s) returned by LSP."""
        if not definitions:
            self.status_bar.show_message("No definition found", timeout=3)
            return
            
        # For now, navigate to the first definition
        definition = definitions[0]
        uri = definition.get('uri', '')
        range_info = definition.get('range', {})
        start = range_info.get('start', {})
        line = start.get('line', 0)
        character = start.get('character', 0)
        
        # Convert file URI to path
        if uri.startswith('file://'):
            file_path = uri[7:]  # Remove 'file://' prefix
        else:
            file_path = uri
            
        try:
            # Check if we need to open a new file
            if file_path != str(self.editor.current_file):
                success = await self.file_initializer.initialize_file(
                    file_path,
                    self.editor,
                    self.output_panel,
                    self.status_bar
                )
                if not success:
                    self.output_panel.add_error(f"Failed to open file: {file_path}")
                    return
            
            # Navigate to the definition position
            self.editor.cursor_location = (line, character)
            self.status_bar.show_message(f"Navigated to definition at line {line + 1}, column {character + 1}", timeout=2)
            
        except FileNotFoundError:
            error_msg = f"Definition file not found: {file_path}"
            self.output_panel.add_error(error_msg)
            self.status_bar.show_message("Definition file not found", timeout=3)
        except PermissionError:
            error_msg = f"Permission denied accessing definition file: {file_path}"
            self.output_panel.add_error(error_msg)
            self.status_bar.show_message("Permission denied", timeout=3)
        except ValueError as e:
            error_msg = f"Invalid cursor position for navigation: {e}"
            self.output_panel.add_error(error_msg)
            self.status_bar.show_message("Invalid navigation position", timeout=3)
        except AttributeError as e:
            error_msg = f"Editor or file initializer method not available: {e}"
            self.output_panel.add_error(error_msg)
            self.status_bar.show_message("Navigation method unavailable", timeout=3)
        except Exception as e:
            error_msg = f"Unexpected error navigating to definition: {str(e)}"
            self.output_panel.add_error(error_msg)
            self.status_bar.show_message("Failed to navigate to definition", timeout=3)

    async def on_key(self, event) -> None:
        """Handle key presses to dismiss hover."""
        # Dismiss hover on any key press
        if hasattr(self, 'hover_widget') and self.hover_widget.is_visible():
            await self.hover_widget.hide_hover()
        
        # Cancel any pending hover request
        if hasattr(self, '_hover_timer') and self._hover_timer is not None:
            self._hover_timer.stop()
            self._hover_timer = None
    
    def compose(self) -> ComposeResult:
        """Create the UI layout with resizable panels."""
        with Vertical():
            yield Header()
            
            # Main content area with editor and file explorer
            with Horizontal(id="main-content"):
                # File explorer with initial width (resizable)
                self.file_explorer.styles.width = 25
                self.file_explorer.styles.min_width = 20
                yield self.file_explorer
                
                # Main editor panel with flexible width
                with Vertical(id="main-panel") as main_panel:
                    self.editor.styles.overflow_x = "hidden"
                    self.editor.styles.overflow_y = "auto"
                    yield self.editor
                    with Horizontal(id="ai-panel") as ai_panel:
                        # Left container for selectors
                        with Vertical(id="selector-container"):
                            yield self.ai_mode_selector
                            yield self.ai_model_selector
                        # Right side command bar
                        yield self.command_bar

                    # Output panel on the right
                yield self.output_panel
            
            # Terminal panel (initially hidden)
            yield self.terminal_panel
            
            yield self.status_bar
            yield self.hover_widget
            yield self.file_path_display


    async def on_file_explorer_file_selected(self, message: FileExplorer.FileSelected) -> None:
        """Handle file selection from the file explorer."""
        file_path = message.file_path
        await self.logger.info(f"File selected from explorer: {file_path}")
        
        if Path(file_path).is_file():
            await self.open_path(file_path)
        else:
            # It's a directory, keep the tree view
            await self.logger.debug(f"Directory selected: {file_path}")
    
    async def _add_file_to_context(self, file_path: str) -> None:
        """Add file to AI agent context."""
        if not self.agent_integration:
            error_msg = "Agentic system not initialized"
            await self.logger.error(error_msg)
            self.output_panel.add_error(error_msg)
            return
        
        try:
            # Read file content asynchronously
            import aiofiles
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
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
    
    async def action_toggle_terminal(self) -> None:
        """Toggle terminal panel visibility."""
        await self.logger.debug("User triggered terminal toggle")
        await self.terminal_panel.toggle_visibility()
        
        # Focus terminal if it's now visible
        if self.terminal_panel.is_visible:
            self.terminal_panel.focus()
    
    # Search & Replace Actions
    async def action_find(self) -> None:
        """Open find dialog."""
        await self.logger.debug("Opening find dialog")
        if self.current_search_dialog:
            self.current_search_dialog.dismiss()
        
        dialog = SearchReplaceDialog(self.search_manager, self.editor, mode="find")
        self.current_search_dialog = dialog
        await self.push_screen(dialog)
    
    async def action_find_next(self) -> None:
        """Find next occurrence."""
        await self.logger.debug("Finding next occurrence")
        if hasattr(self.search_manager, 'current_query') and self.search_manager.current_query:
            result = self.search_manager.find_next_match(self.editor.text, self.search_manager.current_query)
            if result:
                self.editor.cursor_location = (result.line, result.start_col)
                self.editor.selection = Selection(start=(result.line, result.start_col), end=(result.line, result.end_col))
    
    async def action_find_previous(self) -> None:
        """Find previous occurrence."""
        await self.logger.debug("Finding previous occurrence")
        if hasattr(self.search_manager, 'current_query') and self.search_manager.current_query:
            result = self.search_manager.find_previous_match(self.editor.text, self.search_manager.current_query)
            if result:
                self.editor.cursor_location = (result.line, result.start_col)
                self.editor.selection = Selection(start=(result.line, result.start_col), end=(result.line, result.end_col))
    
    async def action_replace(self) -> None:
        """Open replace dialog."""
        await self.logger.debug("Opening replace dialog")
        if self.current_search_dialog:
            self.current_search_dialog.dismiss()
        
        dialog = SearchReplaceDialog(self.search_manager, self.editor, mode="replace")
        self.current_search_dialog = dialog
        await self.push_screen(dialog)
    
    async def action_replace_all(self) -> None:
        """Open replace all dialog."""
        await self.logger.debug("Opening replace all dialog")
        if self.current_search_dialog:
            self.current_search_dialog.dismiss()
        
        dialog = SearchReplaceDialog(self.search_manager, self.editor, mode="replace_all")
        self.current_search_dialog = dialog
        await self.push_screen(dialog)
    
    async def action_find_in_files(self) -> None:
        """Open find in files dialog."""
        await self.logger.debug("Opening find in files dialog")
        if self.current_search_dialog:
            self.current_search_dialog.dismiss()
        
        dialog = FindInFilesDialog()
        self.current_search_dialog = dialog
        await self.push_screen(dialog)
    
    # View & Layout Actions
    async def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility."""
        await self.logger.debug("Toggling sidebar")
        self.sidebar_visible = not self.sidebar_visible
        # Update CSS classes or visibility
        if hasattr(self.file_explorer, 'display'):
            self.file_explorer.display = self.sidebar_visible
        self.refresh()
    
    async def action_toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        await self.logger.debug("Toggling fullscreen mode")
        self.fullscreen_mode = not self.fullscreen_mode
        # Implementation depends on terminal capabilities
        # For now, just log the action
        if self.fullscreen_mode:
            self.output_panel.add_info("Entered fullscreen mode")
        else:
            self.output_panel.add_info("Exited fullscreen mode")
    
    async def action_zoom_in(self) -> None:
        """Zoom in."""
        await self.logger.debug("Zooming in")
        self.zoom_level = min(self.zoom_level + 0.1, 3.0)
        self.output_panel.add_info(f"Zoom level: {self.zoom_level:.1f}")
        # Implementation would depend on terminal/display capabilities
    
    async def action_zoom_out(self) -> None:
        """Zoom out."""
        await self.logger.debug("Zooming out")
        self.zoom_level = max(self.zoom_level - 0.1, 0.5)
        self.output_panel.add_info(f"Zoom level: {self.zoom_level:.1f}")
        # Implementation would depend on terminal/display capabilities
    
    # Advanced Actions
    async def action_run_current_file(self) -> None:
        """Run the current file."""
        await self.logger.debug("Running current file")
        if not self.editor.current_file:
            self.output_panel.add_error("No file is currently open")
            return
        
        file_path = str(self.editor.current_file)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Determine how to run the file based on extension
        if file_ext == '.py':
            command = f"python {file_path}"
        elif file_ext == '.js':
            command = f"node {file_path}"
        elif file_ext == '.nim':
            command = f"nim c -r {file_path}"
        else:
            self.output_panel.add_error(f"Don't know how to run files with extension: {file_ext}")
            return
        
        self.output_panel.add_info(f"Running: {command}")
        # Here you would integrate with terminal panel to run the command
        if hasattr(self.terminal_panel, 'run_command'):
            await self.terminal_panel.run_command(command)
    
    async def action_format_code(self) -> None:
        """Format the current code."""
        await self.logger.debug("Formatting code")
        if not self.editor.current_file:
            self.output_panel.add_error("No file is currently open")
            return
        
        file_path = str(self.editor.current_file)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Determine formatter based on file extension
        if file_ext == '.py':
            # Use black or autopep8
            self.output_panel.add_info("Formatting Python code...")
            # Implementation would call formatter and update editor content
        elif file_ext == '.js' or file_ext == '.ts':
            # Use prettier
            self.output_panel.add_info("Formatting JavaScript/TypeScript code...")
        else:
            self.output_panel.add_info(f"No formatter configured for {file_ext} files")
        
        # For now, just show a message
        self.output_panel.add_info("Code formatting completed")
    
    async def action_show_settings(self) -> None:
        """Show the AI model settings modal."""
        await self.logger.debug("Opening settings modal")
        try:
            modal = SettingsModal(logger=self.logger)
            await self.push_screen(modal)
            await self.logger.debug("Settings modal opened successfully")
        except Exception as e:
            await self.logger.error(f"Failed to open settings modal: {e}")
            self.output_panel.add_error(f"Failed to open settings: {e}")
    
    async def on_terminal_panel_toggle_visibility(self, message: TerminalPanel.ToggleVisibility) -> None:
        """Handle terminal panel visibility toggle messages."""
        await self.logger.info(f"Terminal panel visibility changed: {message.visible}")
        
        # Update layout if needed
        if message.visible:
            await self.logger.debug("Terminal panel is now visible")
        else:
            await self.logger.debug("Terminal panel is now hidden")
    
    async def _update_status_bar(self):
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
            await self.status_bar.update_from_editor(editor_content, current_file)
            
            # Force refresh of status bar
            self.status_bar.refresh()
    

    
    async def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        try:
            await self.logger.info("Shutting down K2EditApp")
            
            # Clean up terminal panel first (has subprocess)
            if hasattr(self, 'terminal_panel'):
                try:
                    await self.terminal_panel.cleanup()
                except Exception as e:
                    await self.logger.error(f"Error cleaning up terminal panel: {e}")
            
            # Shutdown task queue
            if self._task_queue:
                try:
                    await self._task_queue.stop()
                except Exception as e:
                    await self.logger.error(f"Error shutting down task queue: {e}")
            
            # Shutdown thread pool
            if hasattr(self, 'thread_pool'):
                try:
                    self.thread_pool.shutdown()
                except Exception as e:
                    await self.logger.error(f"Error shutting down thread pool: {e}")
            
            # Shutdown agentic system
            if self.agent_integration:
                try:
                    await self.agent_integration.shutdown()
                except Exception as e:
                    await self.logger.error(f"Error shutting down agent integration: {e}")
            
            # Shutdown logger last, with error handling
            try:
                await self.logger.shutdown()
            except Exception as e:
                # If logger shutdown fails, print to stderr as fallback
                print(f"Warning: Logger shutdown failed: {e}", file=sys.stderr)
                
        except Exception as e:
            # Final fallback error handling
            print(f"Error during application shutdown: {e}", file=sys.stderr)


    async def show_diagnostics_modal(self, diagnostics: list[Dict[str, Any]]) -> None:
        """Direct method to show diagnostics modal, bypassing message system."""
        await self.logger.debug("=== SHOW_DIAGNOSTICS_MODAL CALLED DIRECTLY ===")
        await self.logger.debug(f"Diagnostics count: {len(diagnostics)}")
        
        try:
            modal = DiagnosticsModal(diagnostics, logger=self.logger)
            await self.logger.debug("Created DiagnosticsModal successfully")
            await self.push_screen(modal)
            await self.logger.debug("Pushed DiagnosticsModal to screen via direct method")
            await self.logger.debug("=== DIAGNOSTICS MODAL DISPLAYED VIA DIRECT CALL ===")
        except Exception as e:
            await self.logger.error(f"Failed to show diagnostics modal via direct call: {e}")
            import traceback
            await self.logger.error(traceback.format_exc())

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
            
            # Switch branch using async subprocess
            process = await asyncio.create_subprocess_exec(
                "git", "checkout", message.branch_name,
                cwd=current_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=10.0
                )
                stdout_text = stdout.decode('utf-8') if stdout else ''
                stderr_text = stderr.decode('utf-8') if stderr else ''
                
                if process.returncode == 0:
                    self.output_panel.add_info(f"Switched to branch: {message.branch_name}")
                    await self.status_bar._update_git_branch()  # Refresh branch display
                else:
                    error_msg = f"Failed to switch branch: {stderr_text}"
                    self.output_panel.add_error(error_msg)
                    await self.logger.error(error_msg)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error_msg = "Git checkout timed out after 10 seconds"
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
    
    async def on_ai_mode_selector_mode_selected(self, message: AIModeSelector.ModeSelected) -> None:
        """Handle AI mode selection."""
        self.current_ai_mode = message.mode
        await self.logger.info(f"AI mode changed to: {message.mode}")
        
        # Update command bar with the new mode
        if hasattr(self.command_bar, 'set_ai_mode'):
            self.command_bar.set_ai_mode(message.mode)
    
    async def on_ai_model_selector_model_selected(self, message: AIModelSelector.ModelSelected) -> None:
        """Handle AI model selection."""
        await self.logger.info(f"AI model changed to: {message.model_name} ({message.model_id})")
        
        # Update the agent integration with the new model
        if self.agent_integration:
            await self.agent_integration.set_current_model(message.model_id)
        
        # Update the KimiAPI with the new model settings
        if self.kimi_api:
            await self._update_api_with_model(message.model_id)
        
        # Update command bar with the new model if it supports it
        if hasattr(self.command_bar, 'set_ai_model'):
            self.command_bar.set_ai_model(message.model_id, message.model_name)
    
    async def _update_api_with_model(self, model_id: str) -> None:
        """Update API configuration with the selected model."""
        try:
            from .utils.settings_manager import SettingsManager
            settings_manager = SettingsManager()
            api_address, api_key = await settings_manager.get_api_settings(model_id)
            
            if api_address and api_key:
                # Update KimiAPI configuration
                if hasattr(self.kimi_api, 'update_config'):
                    await self.kimi_api.update_config(api_address, api_key, model_id)
                await self.logger.info(f"Updated API configuration for model: {model_id}")
            else:
                await self.logger.warning(f"No API configuration found for model: {model_id}")
                self.output_panel.add_warning(f"No API configuration found for {model_id}. Please configure in Settings.")
        except Exception as e:
            await self.logger.error(f"Failed to update API configuration: {e}")
            self.output_panel.add_error(f"Failed to update API configuration: {e}")


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
        # Validate initial file path
        if initial_file:
            path = Path(initial_file)
            if not path.exists():
                print(f"Error: File or directory '{initial_file}' does not exist")
                sys.exit(1)
            # If it's a directory, we'll let the application handle it
            # The FileInitializer will handle directory vs file logic

    # Create and run the application with proper cleanup
    app = K2EditApp(initial_file=initial_file, logger=logger)
    app.run()


if __name__ == "__main__":
    main()