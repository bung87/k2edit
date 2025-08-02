"""
File Explorer component for the K2Edit application.

This module provides a tree-style file explorer widget that allows users
to browse and open files from the filesystem.
"""

import os
from pathlib import Path
from typing import Optional, List
import logging

from textual.widgets import Tree, Static
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.message import Message


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
    """
    
    current_path = reactive(Path.cwd())
    
    def __init__(self, root_path: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        
        self.root_path = root_path or Path.cwd()
        self.current_path = self.root_path
        self.logger = logging.getLogger("k2edit.file_explorer")
    
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
        try:
            self._add_directory(tree.root, self.root_path)
        except Exception as e:
            self.logger.error(f"Error building tree: {e}")
    
    def _add_directory(self, parent: TreeNode, path: Path) -> None:
        """Add a directory and its contents to the tree."""
        try:
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
                    file_node = parent.add(item.name)
                    file_node.label_style = "file"
                    file_node.data = {"type": "file", "path": str(item)}
                    
        except PermissionError:
            self.logger.warning(f"Permission denied accessing {path}")
        except Exception as e:
            self.logger.error(f"Error adding directory {path}: {e}")
    
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        node = event.node
        if node.data:
            item_type = node.data.get("type")
            item_path = node.data.get("path")
            
            if item_type == "file" and item_path:
                # Send file selected message
                self.post_message(self.FileSelected(item_path))
    
    class FileSelected(Message):
        """Message sent when a file is selected in the explorer."""
        
        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path
    
    def refresh_explorer(self) -> None:
        """Refresh the entire file explorer."""
        tree = self.query_one(Tree)
        tree.clear()
        self._build_tree(tree)
    
    def set_root_path(self, path: Path) -> None:
        """Set a new root path for the explorer."""
        self.root_path = path
        self.current_path = path
        self.refresh_explorer()