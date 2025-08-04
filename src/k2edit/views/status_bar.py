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
        print(f"StatusBar render() called - git_branch: '{self.git_branch}', cursor: ({self.cursor_line}, {self.cursor_column})")
        
        # Always show at least basic info
        result = f"K2Edit | Ln {self.cursor_line}, Col {self.cursor_column} | {self.language or 'Text'}"
        
        # Add git branch if available
        if self.git_branch:
            result = f"🌿 {self.git_branch} | " + result
        
        # Add diagnostics if available
        if self.diagnostics_errors > 0:
            result = f"❌ {self.diagnostics_errors} | " + result
        
        if self.diagnostics_warnings > 0:
            result = f"⚠️ {self.diagnostics_warnings} | " + result
        
        print(f"StatusBar render result: '{result}'")
        return result
    
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
        print(f"StatusBar update_diagnostics: warnings={warnings}, errors={errors}")
        self.diagnostics_warnings = warnings
        self.diagnostics_errors = errors
        self.refresh()
    
    def update_cursor_position(self, line: int, column: int):
        """Update cursor position."""
        print(f"StatusBar update_cursor_position: ({line}, {column})")
        self.cursor_line = line
        self.cursor_column = column
        self.refresh()
    
    def update_file_info(self, file_path: str = "", language: str = "", 
                        indentation: str = "", encoding: str = "", 
                        line_ending: str = ""):
        """Update file-related information."""
        print(f"StatusBar update_file_info: file='{file_path}', lang='{language}', indent='{indentation}'")
        self.file_path = file_path
        self.language = language
        self.indentation = indentation
        self.encoding = encoding
        self.line_ending = line_ending
        self.refresh()
    
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
        print("StatusBar on_mount called")
        
        # Initialize git branch
        self._update_git_branch_sync()
        
        # Force initial render
        self.refresh()
        
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