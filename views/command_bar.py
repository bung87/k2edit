"""Command bar widget for handling user commands and AI interactions."""

import asyncio
import logging
from typing import Optional
from textual.widgets import Input
from textual.message import Message
from textual import events


class CommandBar(Input):
    """Command input widget with command processing."""
    
    def __init__(self, **kwargs):
        super().__init__(
            placeholder="Type a command (e.g., /kimi, /open, /save)...",
            **kwargs
        )
        self.editor = None
        self.kimi_api = None
        self.agent_integration = None
        self.logger = logging.getLogger("k2edit")
    
    class CommandExecuted(Message):
        """Message sent when a command is executed."""
        def __init__(self, command: str, result: str) -> None:
            self.command = command
            self.result = result
            super().__init__()
    
    def set_editor(self, editor) -> None:
        """Set the editor reference."""
        self.editor = editor
    
    def set_kimi_api(self, kimi_api) -> None:
        """Set the Kimi API reference."""
        self.kimi_api = kimi_api
    
    def set_agent_integration(self, agent_integration) -> None:
        """Set the agent integration reference."""
        self.agent_integration = agent_integration
    
    def set_text(self, text: str) -> None:
        """Set the command bar text."""
        self.value = text
        self.cursor_position = len(text)
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission."""
        command = event.value.strip()
        if not command:
            return
        
        # Clear the input
        self.value = ""
        
        # Process the command
        await self._process_command(command)
    
    async def _process_command(self, command: str) -> None:
        """Process and execute a command."""
        self.logger.info(f"Processing command: {command}")
        
        if not command.startswith('/'):
            # Treat as a Kimi query
            await self._handle_kimi_query(command)
            return
        
        parts = command[1:].split(' ', 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        try:
            if cmd == "open":
                await self._handle_open(args)
            elif cmd == "save":
                await self._handle_save(args)
            elif cmd == "saveas":
                await self._handle_save_as(args)
            elif cmd == "kimi":
                await self._handle_kimi_query(args)
            elif cmd == "explain":
                await self._handle_explain()
            elif cmd == "fix":
                await self._handle_fix()
            elif cmd == "refactor":
                await self._handle_refactor(args)
            elif cmd == "generate_test":
                await self._handle_generate_test()
            elif cmd == "doc":
                await self._handle_doc()
            elif cmd == "run_agent":
                await self._handle_run_agent(args)
            elif cmd == "help":
                await self._handle_help()
            else:
                self.app.notify(f"Unknown command: {cmd}", severity="warning")
        
        except Exception as e:
            self.logger.error(f"Error executing command '{command}': {e}", exc_info=True)
            self.app.notify(f"Error executing command: {e}", severity="error")
    
    async def _handle_open(self, filename: str) -> None:
        """Handle file open command."""
        if not filename:
            self.app.notify("Please specify a filename", severity="warning")
            return
        
        if self.editor:
            success = self.editor.load_file(filename)
            if success:
                self.logger.info(f"Successfully opened file: {filename}")
                self.app.notify(f"Opened: {filename}", severity="information")
    
    async def _handle_save(self, filename: str = "") -> None:
        """Handle file save command."""
        if self.editor:
            success = self.editor.save_file(filename if filename else None)
            if success:
                self.logger.info(f"Successfully saved file: {filename or self.editor.current_file}")
            elif not success and not filename:
                self.app.notify("Use /saveas <filename> for new files", severity="warning")
    
    async def _handle_save_as(self, filename: str) -> None:
        """Handle save as command."""
        if not filename:
            self.app.notify("Please specify a filename", severity="warning")
            return
        
        if self.editor:
            self.editor.save_file(filename)
            self.logger.info(f"Successfully saved file as: {filename}")
    
    async def _handle_kimi_query(self, query: str) -> None:
        """Handle general Kimi query."""
        if not query:
            self.app.notify("Please provide a query", severity="warning")
            return
        
        if not self.kimi_api:
            self.app.notify("Kimi API not available", severity="error")
            return
        
        # Get current context
        context = self._get_editor_context()
        
        # Show loading message
        self.app.notify("Asking Kimi...", severity="information")
        
        try:
            response = await self.kimi_api.chat(
                query,
                context=context,
                use_tools=True
            )
            
            # Handle tool calls if present
            if response.get('tool_calls'):
                await self._handle_tool_calls(response['tool_calls'])
            
            # Post the response
            self.post_message(self.CommandExecuted(f"/kimi {query}", response.get('content', '')))
            
        except Exception as e:
            self.logger.error(f"Kimi API error for query '{query}': {e}", exc_info=True)
            self.app.notify(f"Kimi API error: {e}", severity="error")
    
    async def _handle_explain(self) -> None:
        """Handle code explanation request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            self.app.notify("No code selected", severity="warning")
            return
        
        query = f"Please explain this code:\n\n```\n{selected_text}\n```"
        await self._handle_kimi_query(query)
    
    async def _handle_fix(self) -> None:
        """Handle code fix request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            self.app.notify("No code selected", severity="warning")
            return
        
        query = f"Please analyze and fix any issues in this code:\n\n```\n{selected_text}\n```"
        await self._handle_kimi_query(query)
    
    async def _handle_refactor(self, instructions: str) -> None:
        """Handle code refactoring request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            self.app.notify("No code selected", severity="warning")
            return
        
        refactor_prompt = f"Please refactor this code"
        if instructions:
            refactor_prompt += f" with the following requirements: {instructions}"
        
        query = f"{refactor_prompt}:\n\n```\n{selected_text}\n```"
        await self._handle_kimi_query(query)
    
    async def _handle_generate_test(self) -> None:
        """Handle test generation request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            self.app.notify("No code selected", severity="warning")
            return
        
        query = f"Please generate unit tests for this code:\n\n```\n{selected_text}\n```"
        await self._handle_kimi_query(query)
    
    async def _handle_doc(self) -> None:
        """Handle documentation generation request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            self.app.notify("No code selected", severity="warning")
            return
        
        query = f"Please add appropriate docstrings and comments to this code:\n\n```\n{selected_text}\n```"
        await self._handle_kimi_query(query)
    
    async def _handle_run_agent(self, goal: str) -> None:
        """Handle agent mode execution using the integrated agentic system."""
        if not goal:
            self.app.notify("Please specify a goal for the agent", severity="warning")
            return
        
        if not self.agent_integration:
            self.app.notify("Agentic system not initialized", severity="error")
            return
        
        self.app.notify("Running agentic system...", severity="information")
        
        try:
            # Get current editor state
            current_file = str(self.editor.current_file) if self.editor.current_file else None
            selected_text = self.editor.get_selected_text()
            cursor_pos = {"line": self.editor.cursor_line, "column": self.editor.cursor_column}
            
            # Use the agentic system
            response = await self.agent_integration.on_ai_query(
                query=goal,
                file_path=current_file,
                selected_text=selected_text,
                cursor_position=cursor_pos
            )
            
            # Format and display response
            if isinstance(response, dict):
                content = response.get('response', str(response))
            else:
                content = str(response)
            
            self.post_message(self.CommandExecuted(f"/run_agent {goal}", content))
            
        except Exception as e:
            self.logger.error(f"Agentic system error for goal '{goal}': {e}", exc_info=True)
            self.app.notify(f"Agentic system error: {e}", severity="error")
    
    async def _handle_help(self) -> None:
        """Show help information."""
        help_text = """
Available Commands:

/open <file>     - Open a file
/save           - Save current file
/saveas <file>  - Save as new file
/kimi <query>   - Ask Kimi AI
/explain        - Explain selected code
/fix            - Fix selected code
/refactor [req] - Refactor selected code
/generate_test  - Generate tests for selected code
/doc            - Add documentation to selected code
/run_agent <goal> - Use agentic system with context/memory/LSP
/help           - Show this help

Agentic System Features:
- Context-aware code analysis
- Project-wide understanding
- Code intelligence via LSP
- Memory of previous interactions
- Cross-file symbol analysis

Keyboard Shortcuts:
Ctrl+O - Open file
Ctrl+S - Save file
Ctrl+K - Focus command bar
Esc    - Focus editor
Ctrl+Q - Quit
"""
        self.post_message(self.CommandExecuted("/help", help_text))
    
    def _get_editor_context(self) -> dict:
        """Get current editor context for AI queries."""
        if not self.editor:
            return {}
        
        context = {
            "current_file": str(self.editor.current_file) if self.editor.current_file else None,
            "file_content": self.editor.text,
            "selected_text": self.editor.get_selected_text(),
            "cursor_position": self.editor.cursor_location,
            "language": getattr(self.editor, 'language', 'text')
        }
        
        # Safely handle selection attributes
        try:
            selection = getattr(self.editor, 'selection', None)
            if selection and hasattr(selection, 'is_empty') and not selection.is_empty:
                if hasattr(self.editor, 'get_selected_lines'):
                    start_line, end_line = self.editor.get_selected_lines()
                    context["selected_lines"] = {"start": start_line, "end": end_line}
        except (AttributeError, ValueError):
            pass
        
        return context
    
    async def _handle_tool_calls(self, tool_calls: list) -> None:
        """Handle tool calls from Kimi API response."""
        for tool_call in tool_calls:
            function_name = tool_call.get('function', {}).get('name')
            arguments = tool_call.get('function', {}).get('arguments', {})
            
            try:
                if function_name == "replace_code":
                    await self._tool_replace_code(**arguments)
                elif function_name == "write_file":
                    await self._tool_write_file(**arguments)
                elif function_name == "read_file":
                    await self._tool_read_file(**arguments)
                else:
                    self.app.notify(f"Unknown tool: {function_name}", severity="warning")
            
            except Exception as e:
                self.logger.error(f"Tool execution error for {function_name}: {e}", exc_info=True)
                self.app.notify(f"Tool execution error: {e}", severity="error")
    
    async def _tool_replace_code(self, start_line: int, end_line: int, new_code: str) -> None:
        """Tool: Replace code in the editor."""
        if self.editor:
            self.editor.replace_lines(start_line, end_line, new_code)
            self.app.notify(f"Replaced lines {start_line}-{end_line}", severity="information")
    
    async def _tool_write_file(self, path: str, content: str) -> None:
        """Tool: Write content to a file."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.app.notify(f"Written to {path}", severity="information")
        except Exception as e:
            self.app.notify(f"Failed to write {path}: {e}", severity="error")
    
    async def _tool_read_file(self, path: str) -> str:
        """Tool: Read content from a file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.app.notify(f"Read from {path}", severity="information")
            return content
        except Exception as e:
            self.app.notify(f"Failed to read {path}: {e}", severity="error")
            return ""