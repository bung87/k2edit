#!/usr/bin/env python3
"""Modal dialogs for K2Edit editor."""

from typing import List, Dict, Any
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Label, ListView, ListItem, TextArea
from textual.binding import Binding
from textual import work
from aiologger import Logger


class DiagnosticsModal(ModalScreen[None]):
    """Modal screen to display detailed diagnostics."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]
    
    def __init__(self, diagnostics: List[Dict[str, Any]], logger: Logger = None, **kwargs):
        super().__init__(**kwargs)
        self.diagnostics = diagnostics
        self.logger = logger
    
    def compose(self) -> ComposeResult:
        """Compose the diagnostics modal."""
        with Container(id="diagnostics-modal"):
            yield Label("Diagnostics Details", id="diagnostics-title")
            
            if not self.diagnostics:
                yield Label("No diagnostics found", classes="diagnostic-empty")
            else:
                with Vertical(id="diagnostics-list"):
                    for idx, diagnostic in enumerate(self.diagnostics):
                        severity = diagnostic.get('severity_name', 'Info')
                        message = diagnostic.get('message', '')
                        file_path = diagnostic.get('file_path', '')
                        line = diagnostic.get('line', 0)
                        column = diagnostic.get('column', 0)
                        source = diagnostic.get('source', '')
                        
                        diagnostic_class = "diagnostic-item"
                        if severity.lower() == 'error':
                            diagnostic_class += " diagnostic-error"
                        elif severity.lower() == 'warning':
                            diagnostic_class += " diagnostic-warning"
                        
                        with Container(classes=diagnostic_class):
                            yield Label(
                                f"{severity}: {message}",
                                classes="diagnostic-message"
                            )
                            yield Label(
                                f"{file_path}:{line}:{column}",
                                classes="diagnostic-location"
                            )
                            if source:
                                yield Label(
                                    f"Source: {source}",
                                    classes="diagnostic-source"
                                )
                            yield Button(
                                "Go to location",
                                id=f"navigate-{idx}",
                                classes="diagnostic-navigate"
                            )
            
            yield Button("Close", id="close-button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the diagnostics modal."""
        if event.button.id == "close-button":
            self.dismiss()
        elif event.button.id and event.button.id.startswith("navigate-"):
            try:
                idx = int(event.button.id.split("-")[1])
                if idx < len(self.diagnostics):
                    diagnostic = self.diagnostics[idx]
                    self.app.post_message(
                        NavigateToDiagnostic(
                            diagnostic.get('file_path', ''),
                            diagnostic.get('line', 1),
                            diagnostic.get('column', 1)
                        )
                    )
                    self.dismiss()
            except (ValueError, IndexError):
                pass


class BranchSwitcherModal(ModalScreen[str]):
    """Modal screen to switch git branches."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]
    
    def __init__(self, branches: List[str], current_branch: str, logger: Logger = None, **kwargs):
        super().__init__(**kwargs)
        self.branches = branches
        self.current_branch = current_branch
        self.logger = logger
    
    def compose(self) -> ComposeResult:
        """Compose the branch switcher modal."""
        with Container(id="branch-switcher-modal"):
            yield Label("Switch Git Branch", id="branch-switcher-title")
            
            if not self.branches:
                yield Label("No branches found", classes="branch-empty")
            else:
                with ListView(id="branch-list"):
                    for branch in self.branches:
                        item_text = f"{branch} (current)" if branch == self.current_branch else branch
                        yield ListItem(
                            Label(item_text),
                            id=f"branch-{branch}"
                        )
            
            yield Button("Cancel", id="cancel-button")
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle branch selection."""
        if event.item and event.item.id and event.item.id.startswith("branch-"):
            branch_name = event.item.id[7:]  # Remove "branch-" prefix
            if branch_name != self.current_branch:
                self.dismiss(branch_name)
            else:
                self.dismiss()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the branch switcher."""
        if event.button.id == "cancel-button":
            self.dismiss()


# Import the message classes from status_bar
from .status_bar import NavigateToDiagnostic