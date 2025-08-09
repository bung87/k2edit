#!/usr/bin/env python3
"""Status bar widget for K2Edit editor."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from textual.widget import Widget
from textual.widgets import Static, Button
from textual.containers import Horizontal, Container, HorizontalScroll
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.message import Message
from textual.screen import Screen
from textual import work
from aiologger import Logger
import asyncio
import chardet
from ..utils.language_utils import detect_language_from_file_path
from ..utils.file_utils import detect_encoding

class GitBranchSwitch(Message):
    """Message to request git branch switching."""
    def __init__(self, branch_name: str) -> None:
        self.branch_name = branch_name
        super().__init__()


class NavigateToDiagnostic(Message):
    """Message to navigate to a diagnostic location."""
    def __init__(self, file_path: str, line: int, column: int) -> None:
        self.file_path = file_path
        self.line = line
        self.column = column
        super().__init__()


class ShowDiagnosticsDetails(Message):
    """Message to show diagnostics details."""
    def __init__(self, diagnostics: List[Dict[str, Any]]) -> None:
        self.diagnostics = diagnostics
        super().__init__()


class StatusBar(Widget):
    """Status bar widget displaying file and editor information."""

    # Reactive properties that will trigger updates
    git_branch = reactive("")
    diagnostics_warnings = reactive(0)
    diagnostics_errors = reactive(0)
    cursor_line = reactive(1)
    cursor_column = reactive(1)
    indentation = reactive("Spaces: 4")
    encoding = reactive("UTF-8")
    line_ending = reactive("LF")
    language = reactive("")
    file_path = reactive("")
    language_server_status = reactive("Disconnected")
    
    # Additional state for interactive features
    diagnostics_data = reactive([])
    available_branches = reactive([])

    def watch_git_branch(self, git_branch: str) -> None:
        """Watch for git branch changes."""
        if hasattr(self, 'git_branch_widget') and self.git_branch_widget:
            self.git_branch_widget.label = git_branch or "main"

    def watch_cursor_line(self, cursor_line: int) -> None:
        """Watch for cursor line changes."""
        if hasattr(self, 'cursor_pos_widget') and self.cursor_pos_widget:
            self.cursor_pos_widget.update(f"Ln {cursor_line}, Col {self.cursor_column}")

    def watch_cursor_column(self, cursor_column: int) -> None:
        """Watch for cursor column changes."""
        if hasattr(self, 'cursor_pos_widget') and self.cursor_pos_widget:
            self.cursor_pos_widget.update(f"Ln {self.cursor_line}, Col {cursor_column}")

    def watch_diagnostics_warnings(self, warnings: int) -> None:
        """Watch for diagnostics warnings changes."""
        if hasattr(self, 'diagnostics_widget') and self.diagnostics_widget:
            self.diagnostics_widget.label = self._format_diagnostics()

    def watch_diagnostics_errors(self, errors: int) -> None:
        """Watch for diagnostics errors changes."""
        if hasattr(self, 'diagnostics_widget') and self.diagnostics_widget:
            self.diagnostics_widget.label = self._format_diagnostics()

    def watch_language_server_status(self, status: str) -> None:
        """Watch for language server status changes."""
        self.logger.debug(f"watch_language_server_status: {status}")
        if hasattr(self, 'lsp_status_widget') and self.lsp_status_widget:
            new_text = f"LSP: {status}"
            self.lsp_status_widget.update(new_text)
            self.logger.debug(f"Updated LSP status widget to: {new_text}")

    def watch_language(self, language: str) -> None:
        """Watch for language changes."""
        if hasattr(self, 'lang_widget') and self.lang_widget:
            self.lang_widget.update(language or "Text")

    def watch_indentation(self, indentation: str) -> None:
        """Watch for indentation changes."""
        if hasattr(self, 'indent_widget') and self.indent_widget:
            self.indent_widget.update(indentation)

    def watch_encoding(self, encoding: str) -> None:
        """Watch for encoding changes."""
        if hasattr(self, 'encoding_widget') and self.encoding_widget:
            self.encoding_widget.update(encoding)

    def watch_line_ending(self, line_ending: str) -> None:
        """Watch for line ending changes."""
        if hasattr(self, 'line_ending_widget') and self.line_ending_widget:
            self.line_ending_widget.update(line_ending)

    def __init__(self, logger: Logger = None, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger or Logger.with_default_handlers(name='StatusBar')

        # Construct widgets first (before reactive initialization)
        self.git_branch_widget = Button("main", id="git-branch", classes="status-button")
        self.cursor_pos_widget = Static("Ln 1, Col 1", id="cursor-pos", classes="status-item")
        self.diagnostics_widget = Button("✓", id="diagnostics", classes="status-button")
        self.lang_widget = Static("Text", id="lang", classes="status-item")
        self.indent_widget = Static("Spaces: 4", id="indent", classes="status-item")
        self.encoding_widget = Static("UTF-8", id="encoding", classes="status-item")
        self.line_ending_widget = Static("LF", id="line-ending", classes="status-item")
        self.lsp_status_widget = Static("LSP: Disconnected", id="lsp-status", classes="status-item")


    def compose(self) -> ComposeResult:
        """Compose the status bar layout."""
        with Horizontal(id="status-bar"):
            with Horizontal(id="left-section", classes="status-section"):
                yield self.git_branch_widget
                yield Static(" | ", classes="status-separator")
               
                yield self.diagnostics_widget
            with Horizontal(id="right-section", classes="status-section"):
                yield self.cursor_pos_widget
                yield Static(" | ", classes="status-separator")
                yield self.indent_widget
                yield Static(" | ", classes="status-separator")
                yield self.encoding_widget
                yield Static(" | ", classes="status-separator")
                yield self.line_ending_widget
                yield Static(" | ", classes="status-separator")
                yield self.lsp_status_widget
                yield Static(" | ", classes="status-separator")
                yield self.lang_widget
                yield Static(" | ", classes="status-separator")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the status bar."""
        button_id = event.button.id
        await self.logger.debug(f"Button pressed: {button_id}")
        
        if button_id == "git-branch":
            await self.logger.debug("Git branch button clicked")
            self._handle_git_branch_click()
        elif button_id == "diagnostics":
            await self.logger.debug("Diagnostics button clicked via on_button_pressed")
            await self._handle_diagnostics_click()

    def _handle_git_branch_click(self) -> None:
        """Handle git branch button click - show branch switcher."""
        self._show_branch_switcher()

    async def _handle_diagnostics_click(self) -> None:
        """Handle diagnostics button click - show diagnostics details."""
        await self._show_diagnostics_details()

    def _show_branch_switcher(self) -> None:
        """Show a modal to switch git branches."""
        from .modals import BranchSwitcherModal
        
        async def show_modal():
            await self.app.push_screen(
                BranchSwitcherModal(self.available_branches, self.git_branch, logger=self.logger),
                self._handle_branch_selection
            )
        
        # Ensure branches are updated before showing modal
        self._update_available_branches()
        
        # Show modal after a short delay to allow branches to load
        self.set_timer(0.1, lambda: asyncio.create_task(show_modal()))
    
    async def _handle_branch_selection(self, branch_name: str) -> None:
        """Handle branch selection from the modal."""
        if branch_name:
            self.switch_git_branch(branch_name)

    async def _show_diagnostics_details(self) -> None:
        """Show detailed diagnostics information."""
        await self.logger.debug("Diagnostics button clicked!")
        await self.logger.debug(f"StatusBar app reference: {getattr(self, 'app', 'NO APP REF')}")
        await self.logger.debug(f"StatusBar parent: {getattr(self, 'parent', 'NO PARENT')}")
        
        # Always show diagnostics modal, even if no data available
        diagnostics_to_show = self.diagnostics_data if self.diagnostics_data else []
        
        # If no real diagnostics, create a sample to test the modal
        if not diagnostics_to_show:
            diagnostics_to_show = [
                {
                    'file_path': 'test_diagnostics.py',
                    'message': 'No diagnostics available - this is a test message',
                    'severity': 2,
                    'line': 1,
                    'column': 1,
                    'source': 'test',
                    'code': 'NO_DIAG',
                    'severity_name': 'Warning'
                }
            ]
            await self.logger.debug(f"No diagnostics found, using test data with {len(diagnostics_to_show)} items")
        else:
            await self.logger.debug(f"Found {len(diagnostics_to_show)} diagnostics to show")

        await self.logger.debug("About to show diagnostics modal...")
        try:
            # Use direct app method call instead of message posting
            if hasattr(self, 'app') and self.app:
                await self.logger.debug(f"Calling show_diagnostics_modal on app: {self.app}")
                # Try to call the method directly if it exists
                if hasattr(self.app, 'show_diagnostics_modal'):
                    await self.logger.debug("About to call show_diagnostics_modal method directly")
                    try:
                        await self.app.show_diagnostics_modal(diagnostics_to_show)
                        await self.logger.debug("Successfully called show_diagnostics_modal method")
                    except Exception as e:
                        await self.logger.error(f"Error calling show_diagnostics_modal: {e}")
                        import traceback
                        await self.logger.error(traceback.format_exc())
                else:
                    # Fallback to using the message handler directly
                    try:
                        # Import inside the function to avoid circular imports
                        from .modals import DiagnosticsModal
                        
                        async def show_modal():
                            try:
                                modal = DiagnosticsModal(diagnostics_to_show, logger=getattr(self.app, 'logger', None))
                                await self.app.push_screen(modal)
                                await self.logger.debug("Diagnostics modal shown successfully via direct call")
                            except Exception as e:
                                await self.logger.error(f"Error showing modal via direct call: {e}")
                        
                        # Schedule the async call
                        if hasattr(self.app, 'call_later'):
                            self.app.call_later(show_modal)
                        else:
                            # Create task
                            import asyncio
                            asyncio.create_task(show_modal())
                    except ImportError as e:
                        await self.logger.error(f"Failed to import DiagnosticsModal: {e}")
                        # Fallback to message posting
                        self.post_message(ShowDiagnosticsDetails(diagnostics_to_show))
                        
                await self.logger.debug("Diagnostics modal request sent to app")
            else:
                await self.logger.error("No app reference found!")
        except Exception as e:
            await self.logger.error(f"Failed to show diagnostics modal: {e}")
            import traceback
            await self.logger.error(traceback.format_exc())

    @work
    async def _update_available_branches(self) -> None:
        """Update the list of available git branches."""
        try:
            current_dir = Path.cwd()
            
            # Check if we're in a git repository
            git_dir = current_dir / ".git"
            if not git_dir.exists():
                self.available_branches = []
                return
            
            # Get all branches
            result = subprocess.run(
                ["git", "branch", "-a"],
                capture_output=True,
                text=True,
                cwd=current_dir,
                timeout=5
            )
            
            if result.returncode == 0:
                branches = []
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('* '):
                        line = line[2:]  # Remove the '* ' from current branch
                    if line.startswith('remotes/'):
                        continue  # Skip remote branches for now
                    branches.append(line)
                
                self.available_branches = branches
                await self.logger.debug(f"Available branches: {branches}")
            else:
                self.available_branches = []
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            self.available_branches = []
            await self.logger.debug(f"Error getting branches: {e}")

    def switch_git_branch(self, branch_name: str) -> None:
        """Switch to a specific git branch."""
        self.post_message(GitBranchSwitch(branch_name))

    def navigate_to_diagnostic(self, file_path: str, line: int, column: int) -> None:
        """Navigate to a specific diagnostic location."""
        self.post_message(NavigateToDiagnostic(file_path, line, column))

    @work
    async def _update_git_branch(self):
        """Update git branch information."""
        try:
            # Get current directory
            current_dir = Path.cwd()
            
            # Check if we're in a git repository
            git_dir = current_dir / ".git"
            if not git_dir.exists():
                self.git_branch = ""
                await self.logger.debug("Not in a git repository")
                return
            
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=current_dir,
                timeout=5
            )
            
            if result.returncode == 0:
                branch = result.stdout.strip()
                # Only log if branch actually changed
                if branch != self.git_branch:
                    await self.logger.debug(f"Git branch updated: {branch}")
                    self.git_branch = branch
            else:
                if self.git_branch != "":
                    self.git_branch = ""
                    await self.logger.debug("Failed to get git branch")
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            if self.git_branch != "":
                self.git_branch = ""
                await self.logger.debug(f"Error updating git branch: {e}")
    
    def update_diagnostics(self, warnings: int = 0, errors: int = 0):
        """Update diagnostics information."""
        self.diagnostics_warnings = warnings
        self.diagnostics_errors = errors
        # Explicitly update the display
        self.diagnostics_widget.label = self._format_diagnostics()

    async def update_diagnostics_from_lsp(self, diagnostics_data: Optional[Dict[str, Any]] = None):
        """Update diagnostics from LSP server response."""
        if diagnostics_data is None:
            self.diagnostics_warnings = 0
            self.diagnostics_errors = 0
            self.diagnostics_data = []
            # Explicitly update the display when clearing diagnostics
            self.diagnostics_widget.label = self._format_diagnostics()
            return
        
        warnings = 0
        errors = 0
        all_diagnostics = []
        
        # Expect consistent dict format: {'diagnostics': [...], 'file_path': '...'}
        if isinstance(diagnostics_data, dict):
            diagnostics = diagnostics_data.get('diagnostics', [])
            file_path = diagnostics_data.get('file_path', '')
            for diagnostic in diagnostics:
                diagnostic_info = {
                    'file_path': file_path,
                    'message': diagnostic.get('message', ''),
                    'severity': diagnostic.get('severity', 1),
                    'line': diagnostic.get('range', {}).get('start', {}).get('line', 0) + 1,
                    'column': diagnostic.get('range', {}).get('start', {}).get('character', 0) + 1,
                    'source': diagnostic.get('source', ''),
                    'code': diagnostic.get('code', ''),
                    'severity_name': 'Error' if diagnostic.get('severity', 1) == 1 else 'Warning'
                }
                all_diagnostics.append(diagnostic_info)
                
                if diagnostic.get('severity', 1) == 2:  # Warning
                    warnings += 1
                elif diagnostic.get('severity', 1) == 1:  # Error
                    errors += 1
        else:
            # Log unexpected format
            await self.logger.warning(f"Unexpected diagnostics data format: {type(diagnostics_data)}")
            return
        
        # Update reactive properties to trigger watchers
        self.diagnostics_warnings = warnings
        self.diagnostics_errors = errors
        self.diagnostics_data = all_diagnostics
        
        # Explicitly update the display
        self.diagnostics_widget.label = self._format_diagnostics()

    def update_cursor_position(self, line: int, column: int):
        """Update cursor position."""
        self.cursor_line = line
        self.cursor_column = column

    def update_language_server_status(self, status: str):
        """Update language server status in status bar."""
        self.logger.debug(f"update_language_server_status called with: {status}")
        # Update the reactive property to trigger watcher
        self.language_server_status = status
        self.logger.debug(f"Set language_server_status reactive property to: {status}")





    
    def _detect_indentation(self, content: str) -> str:
        """Detect indentation type and size from content."""
        if not content:
            return "Spaces: 4"
        lines = content.splitlines()
        space_indents = []
        tab_lines = 0
        for line in lines:
            if not line.strip():
                continue
            if line.startswith('\t'):
                tab_lines += 1
            elif line.startswith(' '):
                indent_size = len(line) - len(line.lstrip(' '))
                if indent_size > 0:
                    space_indents.append(indent_size)
        if tab_lines and space_indents:
            return "Mixed"
        if tab_lines:
            return "Tabs"
        if not space_indents:
            return "Spaces: 4"
        # Find the most common step size (difference between consecutive indents)
        from math import gcd
        from functools import reduce
        unique_sizes = sorted(set(space_indents))
        if len(unique_sizes) == 1:
            return f"Spaces: {unique_sizes[0]}"
        steps = [j - i for i, j in zip(unique_sizes[:-1], unique_sizes[1:]) if j > i]
        if steps:
            step = reduce(gcd, steps)
            return f"Spaces: {step}"
        return f"Spaces: {unique_sizes[0]}"
    
    def _detect_line_ending(self, content: str) -> str:
        """Detect line ending type from content."""
        if not content:
            return "LF"
        
        if '\r\n' in content:
            return "CRLF"
        elif '\n' in content:
            return "LF"
        else:
            return "LF"
    
    def _detect_encoding(self, content: str) -> str:
        """Detect encoding from file content."""
        return detect_encoding(content)
    
    def _format_diagnostics(self) -> str:
        """Format diagnostics information for display."""
        if self.diagnostics_errors > 0 and self.diagnostics_warnings > 0:
            return f"⚠{self.diagnostics_warnings} ✗{self.diagnostics_errors}"
        elif self.diagnostics_errors > 0:
            return f"✗{self.diagnostics_errors}"
        elif self.diagnostics_warnings > 0:
            return f"⚠{self.diagnostics_warnings}"
        else:
            return "✓"
    
    async def update_from_editor(self, editor_content: str = "", file_path: str = ""):
        """Update status bar from editor content and file path."""
        await self.logger.debug(f"update_from_editor: {file_path}")
        if file_path:
            # Extract just the filename for display
            file_name = os.path.basename(file_path)
            self.file_path = file_name
            
            # Detect language from file extension
            language = detect_language_from_file_path(file_path)
            await self.logger.debug(f"Detected language: {language} for file: {file_path}")
            self.language = language
        
        if editor_content:
            # Detect indentation and line ending from content
            indentation = self._detect_indentation(editor_content)
            line_ending = self._detect_line_ending(editor_content)
            self.indentation = indentation
            self.line_ending = line_ending
            
            # Detect encoding from content
            detected_encoding = self._detect_encoding(editor_content)
            self.encoding = detected_encoding
    
    async def on_mount(self):
        """Called when the widget is mounted."""
        # Sync widgets with initial reactive values
        self.git_branch_widget.label = self.git_branch or "main"
        self.cursor_pos_widget.update(f"Ln {self.cursor_line}, Col {self.cursor_column}")
        self.diagnostics_widget.label = self._format_diagnostics()
        self.lang_widget.update(self.language or "Text")
        self.indent_widget.update(self.indentation)
        self.encoding_widget.update(self.encoding)
        # self.set_interval(1, self.update_from_editor)
        
        # Initialize git branch once on mount
        self._update_git_branch()
        
        # Log initial status
        await self.logger.debug("StatusBar initialization complete")
        await self.logger.debug(f"Initial values - Cursor: {self.cursor_line},{self.cursor_column}, File: {self.file_path}, Lang: {self.language}")
    