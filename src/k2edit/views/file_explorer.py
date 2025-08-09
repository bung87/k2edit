"""
File Explorer component for the K2Edit application.

This module provides a tree-style file explorer widget that allows users
to browse and open files from the filesystem.
"""

import os
from pathlib import Path
from typing import Optional
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.message import Message
from textual.containers import Horizontal
from ..logger import get_logger


class FileExplorer(Static):
    """A file explorer widget for navigating the filesystem."""
    
    DEFAULT_CSS = """
    FileExplorer {
        width: 25%;
        height: 100%;
        background: #1e293b;
        border-right: solid #3b82f6;
        margin: 0;
        padding: 0;
    }
    
    FileExplorer .tree--label {
        color: #f1f5f9;
        text-style: none;
    }
    
    FileExplorer .tree--cursor {
        background: #3b82f6;
        color: #f1f5f9;
    }
    
    FileExplorer .directory {
        color: #60a5fa;
        text-style: bold;
    }
    
    FileExplorer .file {
        color: #f1f5f9;
    }
    
    FileExplorer .hidden {
        color: #64748b;
    }
    
    .add-context-btn {
        background: transparent;
        color: #10b981;
        border: none;
        padding: 0 1;
        margin: 0 1;
        min-width: 3;
        height: 1;
        text-style: none;
    }
    
    .add-context-btn:hover {
        background: #10b981;
        color: #1e293b;
    }
    
    .add-context-btn:focus {
        background: #059669;
        color: #f1f5f9;
    }
    
    .help-text {
        width: 100%;
        height: 1;
        background: #334155;
        color: #94a3b8;
        text-align: center;
        padding: 0 1;
    }
    """
    
    current_path = reactive(Path.cwd())
    
    def __init__(self, root_path: Optional[Path] = None, logger=None, **kwargs):
        super().__init__(**kwargs)
        
        self.root_path = root_path or Path.cwd()
        self.current_path = self.root_path
        self.logger = logger or get_logger()
    
    def compose(self):
        """Compose the file explorer."""
        tree = Tree(str(self.root_path))
        tree.show_root = False
        tree.guide_depth = 3
        
        # Build initial tree
        self._build_tree(tree)
        
        yield tree
    
    def _build_tree(self, tree: Tree) -> None:
        """Build the file tree starting from root_path."""
        self._add_directory(tree.root, self.root_path)
    
    def _add_directory(self, parent: TreeNode, path: Path) -> None:
        """Add a directory and its contents to the tree."""
        # Debug: Check if path is actually a string instead of Path object
        if isinstance(path, str):
            # This is the bug! Convert string to Path object
            path = Path(path)
        
        if not path.exists() or not path.is_dir():
            return
            
        # Get directory contents
        contents = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        
        for item in contents:
            # Skip hidden files and directories
            if item.name.startswith('.'):
                continue
                
            if item.is_dir():
                dir_node = parent.add(item.name, expand=False)
                dir_node.label_style = "directory"
                dir_node.data = {"type": "directory", "path": str(item)}
                # Recursively add subdirectories
                self._add_directory(dir_node, item)
            else:
                file_node = parent.add_leaf(item.name, data={"type": "file", "path": str(item)})
                file_node.label_style = "file"
    
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        node = event.node
        if node.data:
            item_type = node.data.get("type")
            item_path = node.data.get("path")
            
            if item_type == "file" and item_path:
                # Send file selected message
                self.post_message(self.FileSelected(item_path))
    
    def on_key(self, event) -> None:
        """Handle keyboard events for adding files to context."""
        tree = self.query_one(Tree)
        if tree.cursor_node and tree.cursor_node.data:
            node_data = tree.cursor_node.data
            if node_data.get("type") == "file":
                item_path = node_data.get("path")
                
                # Add to context with 'a' key
                if event.key == "a":
                    self.post_message(self.AddToContext(item_path))
                    self.notify(f"Added {Path(item_path).name} to AI context")
    
    def on_tree_node_highlighted(self, event) -> None:
        """Handle node highlighting to show keyboard hints."""
        tree = self.query_one(Tree)
        if tree.cursor_node and tree.cursor_node.data:
            node_data = tree.cursor_node.data
            if node_data.get("type") == "file":
                # Show hint for keyboard shortcut
                self.notify("Press 'a' to add file to AI context", timeout=2.0)
    
    class FileSelected(Message):
        """Message sent when a file is selected in the explorer."""
        
        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path
    
    class AddToContext(Message):
        """Message sent when a file should be added to AI context."""
        
        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path
    
    def refresh_explorer(self) -> None:
        """Refresh the entire file explorer."""
        tree = self.query_one(Tree)
        tree.clear()
        self._build_tree(tree)
    
    async def set_root_path(self, path: Path) -> None:
        """Set a new root path for the explorer."""
        from ..utils.path_validation import validate_directory_path
        
        # Debug logging to track path types
        await self.logger.debug(f"set_root_path called with path type: {type(path)}, value: {path}")
        
        # Validate directory path
        is_valid, error_msg = validate_directory_path(str(path), allow_create=False)
        if not is_valid:
            # Log error but don't crash - fall back to current working directory
            await self.logger.error(f"Invalid root path: {error_msg}. Using current directory.")
            path = Path.cwd()
        
        # Debug logging before assignment
        await self.logger.debug(f"About to set self.root_path to type: {type(path)}, value: {path}")
        
        self.root_path = path
        self.current_path = path
        
        # Debug logging after assignment
        await self.logger.debug(f"self.root_path is now type: {type(self.root_path)}, value: {self.root_path}")
        
        self.refresh_explorer()