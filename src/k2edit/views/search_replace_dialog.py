#!/usr/bin/env python3
"""Search and Replace dialog widget for K2Edit."""

import re
from typing import Optional, List, Tuple
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Button, Checkbox, Static, Label
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.message import Message


class SearchReplaceDialog(ModalScreen):
    """Modal dialog for search and replace functionality."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("f3", "find_next", "Find Next"),
        Binding("shift+f3", "find_previous", "Find Previous"),
        Binding("ctrl+h", "focus_replace", "Replace"),
        Binding("ctrl+shift+h", "replace_all", "Replace All"),
    ]
    
    class SearchResult(Message):
        """Message sent when search is performed."""
        def __init__(self, pattern: str, case_sensitive: bool, regex: bool, direction: str = "next") -> None:
            self.pattern = pattern
            self.case_sensitive = case_sensitive
            self.regex = regex
            self.direction = direction
            super().__init__()
    
    class ReplaceResult(Message):
        """Message sent when replace is performed."""
        def __init__(self, pattern: str, replacement: str, case_sensitive: bool, regex: bool, replace_all: bool = False) -> None:
            self.pattern = pattern
            self.replacement = replacement
            self.case_sensitive = case_sensitive
            self.regex = regex
            self.replace_all = replace_all
            super().__init__()
    
    def __init__(self, mode: str = "find", initial_text: str = "", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode  # "find" or "replace"
        self.initial_text = initial_text
        self.current_matches = []
        self.current_match_index = -1
    
    def compose(self) -> ComposeResult:
        """Compose the search/replace dialog."""
        with Vertical(id="search-replace-dialog"):
            yield Label("Find" if self.mode == "find" else "Find & Replace", id="dialog-title")
            
            # Search input
            with Horizontal(classes="input-row"):
                yield Label("Find:", classes="input-label")
                yield Input(placeholder="Search text...", id="search-input", value=self.initial_text)
            
            # Replace input (only in replace mode)
            if self.mode == "replace":
                with Horizontal(classes="input-row"):
                    yield Label("Replace:", classes="input-label")
                    yield Input(placeholder="Replacement text...", id="replace-input")
            
            # Options
            with Horizontal(classes="options-row"):
                yield Checkbox("Case sensitive", id="case-sensitive")
                yield Checkbox("Regular expression", id="regex-mode")
            
            # Buttons
            with Horizontal(classes="button-row"):
                yield Button("Find Next", id="find-next", variant="primary")
                yield Button("Find Previous", id="find-previous")
                if self.mode == "replace":
                    yield Button("Replace", id="replace-one")
                    yield Button("Replace All", id="replace-all", variant="success")
                yield Button("Close", id="close-dialog")
    
    def on_mount(self) -> None:
        """Focus the search input when mounted."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "close-dialog":
            self.dismiss()
        elif button_id == "find-next":
            self._perform_search("next")
        elif button_id == "find-previous":
            self._perform_search("previous")
        elif button_id == "replace-one":
            self._perform_replace(False)
        elif button_id == "replace-all":
            self._perform_replace(True)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "search-input":
            self._perform_search("next")
        elif event.input.id == "replace-input":
            self._perform_replace(False)
    
    def _perform_search(self, direction: str = "next") -> None:
        """Perform search operation."""
        search_input = self.query_one("#search-input", Input)
        case_sensitive = self.query_one("#case-sensitive", Checkbox).value
        regex_mode = self.query_one("#regex-mode", Checkbox).value
        
        pattern = search_input.value.strip()
        if not pattern:
            return
        
        # Send search message to parent
        self.post_message(self.SearchResult(pattern, case_sensitive, regex_mode, direction))
    
    def _perform_replace(self, replace_all: bool = False) -> None:
        """Perform replace operation."""
        search_input = self.query_one("#search-input", Input)
        replace_input = self.query_one("#replace-input", Input)
        case_sensitive = self.query_one("#case-sensitive", Checkbox).value
        regex_mode = self.query_one("#regex-mode", Checkbox).value
        
        pattern = search_input.value.strip()
        replacement = replace_input.value
        
        if not pattern:
            return
        
        # Send replace message to parent
        self.post_message(self.ReplaceResult(pattern, replacement, case_sensitive, regex_mode, replace_all))
    
    def action_find_next(self) -> None:
        """Action for F3 key."""
        self._perform_search("next")
    
    def action_find_previous(self) -> None:
        """Action for Shift+F3 key."""
        self._perform_search("previous")
    
    def action_focus_replace(self) -> None:
        """Action for Ctrl+H key."""
        if self.mode == "replace":
            replace_input = self.query_one("#replace-input", Input)
            replace_input.focus()
    
    def action_replace_all(self) -> None:
        """Action for Ctrl+Shift+H key."""
        if self.mode == "replace":
            self._perform_replace(True)
    
    def action_dismiss(self) -> None:
        """Close the dialog."""
        self.dismiss()


class FindInFilesDialog(ModalScreen):
    """Modal dialog for find in files functionality."""

    BINDINGS = [
        Binding("escape", "close_dialog", "Close"),
        Binding("enter", "search_files", "Search"),
    ]
    
    def __init__(self, initial_text: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.initial_text = initial_text
        self.case_sensitive_active = False
        self.regex_mode_active = False
    
    class SearchInFilesResult(Message):
        """Message sent when search in files is performed."""
        def __init__(self, pattern: str, file_pattern: str, case_sensitive: bool, regex: bool) -> None:
            self.pattern = pattern
            self.file_pattern = file_pattern
            self.case_sensitive = case_sensitive
            self.regex = regex
            super().__init__()
    
    def __init__(self, initial_text: str = "", **kwargs):
        super().__init__(**kwargs)
        self.initial_text = initial_text
    
    def compose(self) -> ComposeResult:
        """Compose the find in files dialog."""
        with Vertical(id="find-in-files-dialog"):
            # Dialog title with icon
            yield Label("🔍 Find in Files", id="dialog-title")
            
            # Search section with inline options
            yield Label("Search Pattern", classes="section-header")
            with Horizontal(classes="search-row"):
                yield Label("🔍", classes="input-icon")
                yield Input(placeholder="Enter search text...", id="search-input", value=self.initial_text)
                with Horizontal(classes="inline-options"):
                    yield Button("Aa", id="case-sensitive", classes="compact-toggle")
                    yield Button(".*", id="regex-mode", classes="compact-toggle")

            # File pattern section
            yield Label("File Filters", classes="section-header")
            with Horizontal(classes="input-group"):
                yield Label("📂", classes="input-icon")
                yield Input(placeholder="*.py, *.js, etc. (leave empty for all files)", id="file-pattern-input")

            # Action buttons
            with Horizontal(classes="button-group"):
                yield Button("🔍 Search", id="search-files", classes="primary-button")
                yield Button("Close", id="close-dialog", classes="secondary-button")
    
    def on_mount(self) -> None:
        """Focus the search input when mounted."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id == "close-dialog":
            self.dismiss()
        elif button_id == "search-files":
            self._perform_search()
        elif button_id == "case-sensitive":
            self._toggle_case_sensitive()
        elif button_id == "regex-mode":
            self._toggle_regex_mode()
    
    def _toggle_case_sensitive(self) -> None:
        """Toggle case sensitive option."""
        self.case_sensitive_active = not self.case_sensitive_active
        button = self.query_one("#case-sensitive", Button)
        if self.case_sensitive_active:
            button.add_class("toggle-active")
        else:
            button.remove_class("toggle-active")
    
    def _toggle_regex_mode(self) -> None:
        """Toggle regex mode option."""
        self.regex_mode_active = not self.regex_mode_active
        button = self.query_one("#regex-mode", Button)
        if self.regex_mode_active:
            button.add_class("toggle-active")
        else:
            button.remove_class("toggle-active")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        self._perform_search()
    
    def _perform_search(self) -> None:
        """Perform search in files operation."""
        search_input = self.query_one("#search-input", Input)
        file_pattern_input = self.query_one("#file-pattern-input", Input)

        pattern = search_input.value.strip()
        file_pattern = file_pattern_input.value.strip() or "*"
        case_sensitive = self.case_sensitive_active
        regex_mode = self.regex_mode_active

        if not pattern:
            return

        # Send search message to parent
        self.post_message(self.SearchInFilesResult(pattern, file_pattern, case_sensitive, regex_mode))
        self.dismiss()
    
    def action_search_files(self) -> None:
        """Action for Enter key."""
        self._perform_search()
    
    def action_dismiss(self) -> None:
        """Close the dialog."""
        self.dismiss()