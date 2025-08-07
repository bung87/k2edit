"""
File Path Display Widget

A widget to display the current file path relative to project root or absolute path.
"""

from pathlib import Path
from textual.widgets import Static
from textual.reactive import reactive


class FilePathDisplay(Static):
    """Widget to display the current file path."""
    
    DEFAULT_CSS = """
    FilePathDisplay {
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        height: 1;
        overflow-x: hidden;
        overflow-y: hidden;
        text-overflow: ellipsis;
    }
    """
    
    current_file = reactive(None)
    project_root = reactive(None)
    
    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        
    def watch_current_file(self, old_file: str, new_file: str) -> None:
        """React to file changes."""
        self.update_display()
        
    def watch_project_root(self, old_root: str, new_root: str) -> None:
        """React to project root changes."""
        self.update_display()
        
    def update_display(self) -> None:
        """Update the displayed file path."""
        if not self.current_file:
            self.update("No file open")
            return
            
        try:
            file_path = Path(self.current_file)
            
            if self.project_root:
                project_path = Path(self.project_root)
                try:
                    # Try to get relative path
                    relative_path = file_path.relative_to(project_path)
                    self.update(str(relative_path))
                except ValueError:
                    # File is not under project root, use absolute
                    self.update(str(file_path))
            else:
                # No project root, use absolute path
                self.update(str(file_path))
                
        except Exception as e:
            self.update(f"Error: {e}")
            
    def set_file(self, file_path: str) -> None:
        """Set the current file path."""
        self.current_file = file_path
        
    def set_project_root(self, project_root: str) -> None:
        """Set the project root directory."""
        self.project_root = project_root