#!/usr/bin/env python3
"""Status bar widget for K2Edit editor."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Horizontal,Container,HorizontalScroll
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.message import Message
from textual import work
from aiologger import Logger


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

    def watch_git_branch(self, git_branch: str) -> None:
        """Watch for git branch changes."""
        if hasattr(self, 'git_branch_widget'):
            self.git_branch_widget.update(git_branch or "main")

    def watch_cursor_line(self, cursor_line: int) -> None:
        """Watch for cursor line changes."""
        self.logger.debug(f"watch_cursor_line: {cursor_line}")
        if hasattr(self, 'cursor_pos_widget'):
            self._update_cursor_position_display(cursor_line, self.cursor_column)

    def watch_cursor_column(self, cursor_column: int) -> None:
        """Watch for cursor column changes."""
        self.logger.debug(f"watch_cursor_column: {cursor_column}")
        if hasattr(self, 'cursor_pos_widget'):
            self._update_cursor_position_display(self.cursor_line, cursor_column)

    def watch_diagnostics_warnings(self, warnings: int) -> None:
        """Watch for diagnostics warnings changes."""
        if hasattr(self, 'diagnostics_widget'):
            self._update_diagnostics_display()

    def watch_diagnostics_errors(self, errors: int) -> None:
        """Watch for diagnostics errors changes."""
        if hasattr(self, 'diagnostics_widget'):
            self._update_diagnostics_display()

    def watch_language(self, language: str) -> None:
        """Watch for language changes."""
        self.logger.debug(f"watch_language: {language}")
        self.logger.debug(f"hasattr(self, 'lang_widget'): {hasattr(self, 'lang_widget')}")
        if hasattr(self, 'lang_widget'):
            display_text = language or "Text"
            self.logger.debug(f"display_text: {display_text}")
            self.lang_widget.update(display_text)

    def watch_indentation(self, indentation: str) -> None:
        """Watch for indentation changes."""
        if hasattr(self, 'indent_widget'):
            self.indent_widget.update(indentation)

    def watch_encoding(self, encoding: str) -> None:
        """Watch for encoding changes."""
        if hasattr(self, 'encoding_widget'):
            self.encoding_widget.update(encoding)

    def _update_cursor_position_display(self, cursor_line: int, cursor_column: int) -> None:
        """Update cursor position display."""
        self.cursor_pos_widget.update(f"Ln {cursor_line}, Col {cursor_column}")

    def _update_diagnostics_display(self) -> None:
        """Update diagnostics display."""
        self.diagnostics_widget.update(self._format_diagnostics())


    def __init__(self, logger: Logger = None, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger

        # Construct widgets first (before reactive initialization)
        self.git_branch_widget = Static("main", id="git-branch", classes="status-item", shrink=True, expand=True)
        self.cursor_pos_widget = Static("Ln 1, Col 1", id="cursor-pos", classes="status-item", shrink=True, expand=True)
        self.diagnostics_widget = Static("✓", id="diagnostics", classes="status-item", shrink=True, expand=True)
        self.lang_widget = Static("Text", id="lang", classes="status-item", shrink=True, expand=True)
        self.indent_widget = Static("Spaces: 4", id="indent", classes="status-item")
        self.encoding_widget = Static("UTF-8", id="encoding", classes="status-item")


    def compose(self) -> ComposeResult:
        """Compose the status bar layout."""
        with Horizontal(id="status-bar"):
            yield self.git_branch_widget
            yield Static(" | ", classes="status-separator")
            yield self.cursor_pos_widget
            yield Static(" | ", classes="status-separator")
            yield self.diagnostics_widget
            yield Static(" | ", classes="status-separator")
            yield self.lang_widget
            yield Static(" | ", classes="status-separator")
            yield self.indent_widget
            yield Static(" | ", classes="status-separator")
            yield self.encoding_widget
            # yield Static(" | ", classes="status-separator", shrink=True, expand=True)
            # yield self.line_ending_widget

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
                self.git_branch = branch
                self.git_branch_widget.update(branch)
                await self.logger.debug(f"Git branch updated: {branch}")
            else:
                self.git_branch = ""
                self.git_branch_widget.update("")
                await self.logger.debug("Failed to get git branch")
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            self.git_branch = ""
            self.git_branch_widget.update("")
            await self.logger.debug(f"Error updating git branch: {e}")
    
    def update_diagnostics(self, warnings: int = 0, errors: int = 0):
        """Update diagnostics information."""
        self.diagnostics_warnings = warnings
        self.diagnostics_errors = errors

    def update_cursor_position(self, line: int, column: int):
        """Update cursor position."""
        self.cursor_line = line
        self.cursor_column = column


    def _update_diagnostics_display(self):
        """Update the diagnostics display widget."""
        self.diagnostics_widget.update(self._format_diagnostics())

    def _detect_language_from_extension(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        if not file_path:
            return ""
        
        ext_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'JavaScript',
            '.tsx': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.html': 'HTML',
            '.css': 'CSS',
            '.scss': 'SCSS',
            '.json': 'JSON',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.xml': 'XML',
            '.sql': 'SQL',
            '.sh': 'Shell',
            '.md': 'Markdown',
            '.nim': 'Nim'
        }
        
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, "")
    
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
    
    def update_from_editor(self, editor_content: str = "", file_path: str = ""):
        """Update status bar from editor content and file path."""
        self.logger.debug(f"update_from_editor: {file_path}")
        if file_path:
            # Extract just the filename for display
            file_name = os.path.basename(file_path)
            self.file_path = file_name
            
            # Detect language from file extension
            language = self._detect_language_from_extension(file_path)
            self.language = language
        
        if editor_content:
            # Detect indentation and line ending from content
            indentation = self._detect_indentation(editor_content)
            line_ending = self._detect_line_ending(editor_content)
            self.indentation = indentation
            self.line_ending = line_ending
            
            # Update encoding (could be detected from content, for now default to UTF-8)
            self.encoding = "UTF-8"
        
        # Update all displays to reflect changes
        # self._update_all_displays()
    
    async def on_mount(self):
        """Called when the widget is mounted."""
        await self.logger.info("StatusBar mounted")
        await self.logger.info(f"Children: {self.children}")
        # Sync widgets with initial reactive values
        self.git_branch_widget.update(self.git_branch or "main")
        self.cursor_pos_widget.update(f"Ln {self.cursor_line}, Col {self.cursor_column}")
        self.diagnostics_widget.update(self._format_diagnostics())
        self.lang_widget.update(self.language or "Text")
        self.indent_widget.update(self.indentation)
        self.encoding_widget.update(self.encoding)
        # self.set_interval(1, self.update_from_editor)
        # Start periodic git branch updates
        self.set_interval(1, self._update_git_branch)
        
        # Log initial status
        await self.logger.debug("StatusBar initialization complete")
        await self.logger.debug(f"Initial values - Cursor: {self.cursor_line},{self.cursor_column}, File: {self.file_path}, Lang: {self.language}")
    