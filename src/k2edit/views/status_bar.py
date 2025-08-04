#!/usr/bin/env python3
"""Status bar widget for K2Edit editor."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from textual.widget import Widget
from textual.reactive import reactive
from textual.message import Message
from textual import work


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
    
    class StatusUpdated(Message):
        """Message sent when status information is updated."""
        
        def __init__(self, status_data: Dict[str, Any]):
            super().__init__()
            self.status_data = status_data
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.styles.height = 1
        self.styles.dock = "bottom"
        self.styles.background = "#3b82f6"
        self.styles.color = "#f1f5f9"
        self.styles.padding = (0, 1)
    
    def compose(self):
        """Compose the status bar layout."""
        # Status bar is a simple widget that renders its own content
        # No child widgets needed
        return []
    
    def render(self) -> str:
        """Render the status bar content."""
        # Left side: Git branch and diagnostics
        left_items = []
        
        if self.git_branch:
            left_items.append(f"🌿 {self.git_branch}")
        
        if self.diagnostics_errors > 0:
            left_items.append(f"❌ {self.diagnostics_errors}")
        
        if self.diagnostics_warnings > 0:
            left_items.append(f"⚠️ {self.diagnostics_warnings}")
        
        left_side = " | ".join(left_items) if left_items else ""
        
        # Right side: Position, indentation, encoding, line break, language
        right_items = []
        
        if self.cursor_line > 0:
            right_items.append(f"Ln {self.cursor_line}, Col {self.cursor_column}")
        
        if self.indentation:
            right_items.append(self.indentation)
        
        if self.encoding:
            right_items.append(self.encoding)
        
        if self.line_ending:
            right_items.append(self.line_ending)
        
        if self.language:
            right_items.append(self.language)
        
        right_side = " | ".join(right_items) if right_items else ""
        
        # Combine left and right sides with proper spacing
        if left_side and right_side:
            # Calculate padding to push right side to the right
            total_width = self.size.width if self.size else 80
            left_width = len(left_side)
            right_width = len(right_side)
            padding = max(0, total_width - left_width - right_width - 2)  # -2 for separators
            
            return f"{left_side}{' ' * padding} | {right_side}"
        elif left_side:
            return left_side
        elif right_side:
            return right_side
        else:
            return ""
    
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
                self.git_branch = result.stdout.strip()
            else:
                self.git_branch = ""
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            self.git_branch = ""
    
    def update_diagnostics(self, warnings: int = 0, errors: int = 0):
        """Update diagnostics information."""
        self.diagnostics_warnings = warnings
        self.diagnostics_errors = errors
    
    def update_cursor_position(self, line: int, column: int):
        """Update cursor position."""
        self.cursor_line = line
        self.cursor_column = column
    
    def update_file_info(self, file_path: str = "", language: str = "", 
                        indentation: str = "", encoding: str = "", 
                        line_ending: str = ""):
        """Update file-related information."""
        self.file_path = file_path
        self.language = language
        self.indentation = indentation
        self.encoding = encoding
        self.line_ending = line_ending
    
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
        indent_sizes = []
        
        for line in lines:
            if line.strip() and line.startswith(' '):
                # Count leading spaces
                indent_size = len(line) - len(line.lstrip())
                if indent_size > 0:
                    indent_sizes.append(indent_size)
        
        if not indent_sizes:
            return "Spaces: 4"
        
        # Find most common indent size
        from collections import Counter
        indent_counter = Counter(indent_sizes)
        most_common_size = indent_counter.most_common(1)[0][0]
        
        return f"Spaces: {most_common_size}"
    
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
    
    def update_from_editor(self, editor_content: str = "", file_path: str = ""):
        """Update status bar from editor content and file path."""
        if file_path:
            language = self._detect_language_from_extension(file_path)
            self.language = language
        
        if editor_content:
            indentation = self._detect_indentation(editor_content)
            line_ending = self._detect_line_ending(editor_content)
            self.indentation = indentation
            self.line_ending = line_ending
    
    def on_mount(self):
        """Called when the widget is mounted."""
        # Initialize git branch
        self._update_git_branch_sync()
        
        # Start periodic git branch updates
        self.set_interval(10, self._update_git_branch)
    
    def _update_git_branch_sync(self):
        """Synchronous version of git branch update for initialization."""
        try:
            # Get current directory
            current_dir = Path.cwd()
            
            # Check if we're in a git repository
            git_dir = current_dir / ".git"
            if not git_dir.exists():
                self.git_branch = ""
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
                self.git_branch = result.stdout.strip()
            else:
                self.git_branch = ""
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            self.git_branch = "" 