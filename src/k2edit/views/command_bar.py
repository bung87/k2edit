"""Command bar widget for handling user commands and AI interactions."""

import asyncio
import json
from typing import Optional
from aiologger import Logger

from textual import events
from textual.message import Message
from textual.widgets import Input

from ..agent.tools import ToolExecutor

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
        self.logger = Logger(name="k2edit")
        self.tool_executor = ToolExecutor(self.logger, editor_widget=self.editor)
        self.output_panel = None
    
    class CommandExecuted(Message):
        """Message sent when a command is executed."""
        def __init__(self, command: str, result: str) -> None:
            self.command = command
            self.result = result
            super().__init__()
    
    class FileOpened(Message):
        """Message sent when a file is opened via command."""
        def __init__(self, file_path: str) -> None:
            self.file_path = file_path
            super().__init__()
    
    def set_editor(self, editor) -> None:
        """Set the editor reference."""
        self.editor = editor
        if self.tool_executor:
            self.tool_executor.editor = editor
    
    def set_kimi_api(self, kimi_api) -> None:
        """Set the Kimi API reference."""
        self.kimi_api = kimi_api
    
    def set_agent_integration(self, agent_integration) -> None:
        """Set the agent integration reference."""
        self.agent_integration = agent_integration
    
    def set_output_panel(self, output_panel) -> None:
        """Set the output panel reference."""
        self.output_panel = output_panel
    
    def set_text(self, text: str) -> None:
        """Set the command bar text."""
        self.value = text
        self.cursor_position = len(text)
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission."""
        command = event.value.strip()
        if not command:
            return
        
        # Clear the input immediately to prevent duplicate submissions
        self.value = ""
        self.cursor_position = 0
        self.refresh()
        
        # Ensure focus returns to editor to complete the clearing
        if self.editor:
            self.editor.focus()
        
        # Process the command
        await self._process_command(command)
    
    async def _process_command(self, command: str) -> None:
        """Process and execute a command."""
        import uuid
        request_id = str(uuid.uuid4())[:8]
        await self.logger.info(f"Processing command [{request_id}]: {command}")
        
        if not command.startswith('/'):
            # Treat as a Kimi query, but use agentic system for project-wide queries
            if any(keyword in command.lower() for keyword in ['review', 'project', 'release', 'analyze', 'what']):
                await self._handle_run_agent(command)
            else:
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
                await self.logger.warning(f"Unknown command: {cmd}")
        
        except Exception as e:
            await self.logger.error(f"Failed to execute command '{cmd}': {e}", exc_info=True)
            if self.output_panel:
                self.output_panel.add_error(f"Failed to execute command: {cmd}")
    
    async def _handle_open(self, filename: str) -> None:
        """Handle file open command."""
        if not filename:
            await self.logger.warning("Open command issued without filename")
            return
        
        try:
            # Use the main app's centralized open_file method
            success = await self.app.open_path(filename)
            if success:
                # Notify main app about file opening
                self.post_message(self.FileOpened(filename))
        except Exception as e:
            await self.logger.error(f"Error opening file {filename}: {e}", exc_info=True)
    
    async def _handle_save(self, filename: str = "") -> None:
        """Handle file save command."""
        try:
            from ..utils.path_validation import validate_path_for_save
            
            if filename:
                # Validate save path using centralized utility
                is_valid, error_msg = validate_path_for_save(filename)
                if not is_valid:
                    if self.output_panel:
                        self.output_panel.add_error(error_msg)
                    await self.logger.error(error_msg)
                    return
            
            if self.editor:
                success = await self.editor.save_file(filename if filename else None)
                if success:
                    await self.logger.info(f"Successfully saved file: {filename or self.editor.current_file}")
                elif not success and not filename:
                    await self.logger.warning("Save command failed - use /saveas <filename> for new files")
        except Exception as e:
            await self.logger.error(f"Error saving file: {e}", exc_info=True)
    
    async def _handle_save_as(self, filename: str) -> None:
        """Handle save as command."""
        if not filename:
            await self.logger.warning("Save as command issued without filename")
            return
        
        try:
            from ..utils.path_validation import validate_path_for_save
            
            # Validate save path using centralized utility
            is_valid, error_msg = validate_path_for_save(filename)
            if not is_valid:
                if self.output_panel:
                    self.output_panel.add_error(error_msg)
                await self.logger.error(error_msg)
                return
            
            if self.editor:
                await self.editor.save_file(filename)
                await self.logger.info(f"Successfully saved file as: {filename}")
        except Exception as e:
            await self.logger.error(f"Error saving file as {filename}: {e}", exc_info=True)
    
    async def _handle_kimi_query(self, query: str) -> None:
        """Handle general Kimi query."""
        if not query:
            await self.logger.warning("Kimi query issued without query text")
            return

        if not self.kimi_api:
            await self.logger.error("Kimi API not available")
            return

        # Display user query in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response(query, "", streaming=True)
            # Ensure output panel is visible and focused
            self.app.query_one("#output-panel").scroll_visible()

        # Get current context
        context = self._get_editor_context()

        # Show loading message in output panel instead of notification
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_info("Asking Kimi...")

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
            await self.logger.error(f"Kimi API request failed: {e}", exc_info=True)
            if self.output_panel:
                self.output_panel.add_error("Kimi API request failed - please wait and try again")
    
    async def _handle_explain(self) -> None:
        """Handle code explanation request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            self.app.notify("No code selected", severity="warning")
            return
        
        query = f"Please explain this code:\n\n```\n{selected_text}\n```"
        
        # Display explain command in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response("/explain", "")
            self.app.query_one("#output-panel").scroll_visible()
        
        await self._handle_kimi_query(query)
    
    async def _handle_fix(self) -> None:
        """Handle code fix request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            await self.logger.warning("Fix command issued without selected text")
            return
        
        query = f"Please analyze and fix any issues in this code:\n\n```\n{selected_text}\n```"
        
        # Display fix command in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response("/fix", "")
            self.app.query_one("#output-panel").scroll_visible()
        
        await self._handle_kimi_query(query)
    
    async def _handle_refactor(self, instructions: str) -> None:
        """Handle code refactoring request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            await self.logger.warning("Refactor command issued without selected text")
            return
        
        refactor_prompt = f"Please refactor this code"
        if instructions:
            refactor_prompt += f" with the following requirements: {instructions}"
        
        query = f"Please refactor this code:\n\n```\n{selected_text}\n```\n\n{instructions}"
        
        # Display refactor command in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response("/refactor", "")
            self.app.query_one("#output-panel").scroll_visible()
        
        await self._handle_kimi_query(query)
    
    async def _handle_generate_test(self) -> None:
        """Handle test generation request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            await self.logger.warning("Generate test command issued without selected text")
            return
        
        query = f"Please generate unit tests for this code:\n\n```\n{selected_text}\n```\n\nInclude comprehensive test cases covering edge cases and typical usage."
        
        # Display generate test command in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response("/generate_test", "")
            self.app.query_one("#output-panel").scroll_visible()
        
        await self._handle_kimi_query(query)
    
    async def _handle_doc(self) -> None:
        """Handle documentation generation request."""
        if not self.editor:
            return
        
        selected_text = self.editor.get_selected_text()
        if not selected_text.strip():
            await self.logger.warning("Doc command issued without selected text")
            return
        
        query = f"Please add appropriate docstrings and comments to this code:\n\n```\n{selected_text}\n```"
        
        # Display doc command in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response("/doc", "")
            self.app.query_one("#output-panel").scroll_visible()
        
        await self._handle_kimi_query(query)
    
    async def _handle_run_agent(self, goal: str) -> None:
        """Handle agent mode execution using the integrated agentic system."""
        import uuid
        
        if not goal:
            await self.logger.warning("Run agent command issued without goal")
            return

        if not self.agent_integration:
            await self.logger.error("Agentic system not initialized")
            return

        if not self.kimi_api:
            await self.logger.error("Kimi API not available")
            return

        request_id = str(uuid.uuid4())
        
        # Display run agent command in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response(goal, "", streaming=True)
            self.app.query_one("#output-panel").scroll_visible()
            self.output_panel.add_agent_progress(request_id, 0, 10, "started")

        try:
            # Get current editor state
            current_file = str(self.editor.current_file) if self.editor.current_file else None
            selected_text = self.editor.get_selected_text()
            cursor_pos = {"line": self.editor.cursor_line, "column": self.editor.cursor_column}

            # Get enhanced context from agentic system
            agent_result = await self.agent_integration.on_ai_query(
                query=goal,
                file_path=current_file,
                selected_text=selected_text,
                cursor_position=cursor_pos
            )

            # Extract the actual context data from agent result
            context = agent_result.get("context", {})

            # Use Kimi API's agent mode with enhanced context
            def progress_callback(req_id, current, max_iter, status):
                if hasattr(self, 'output_panel') and self.output_panel:
                    self.output_panel.add_agent_progress(req_id, current, max_iter, status)
            
            response = await self.kimi_api.run_agent(
                goal=goal,
                context=context,
                progress_callback=progress_callback
            )

            # Format and display response
            content = response.get('content', str(response))
            final_iterations = response.get('iterations', 10)
            if response.get('error'):
                content = f"Error: {response['error']}"
                if hasattr(self, 'output_panel') and self.output_panel:
                    self.output_panel.add_agent_progress(request_id, final_iterations, final_iterations, "error")
            else:
                if hasattr(self, 'output_panel') and self.output_panel:
                    self.output_panel.add_agent_progress(request_id, final_iterations, final_iterations, "completed")

            self.post_message(self.CommandExecuted(f"/run_agent {goal}", content))

        except Exception as e:
            await self.logger.error(f"Agentic system request failed for goal '{goal}': {e}", exc_info=True)
            if hasattr(self, 'output_panel') and self.output_panel:
                self.output_panel.add_error("Agentic system request failed")
                self.output_panel.add_agent_progress(request_id, 0, 10, "error")
    
    async def _handle_help(self) -> None:
        """Display help information."""
        help_text = """
K2Edit - AI-Enhanced Code Editor

Commands:
- /kimi <query> - Ask Kimi AI a question about your code
- /run_agent <goal> - Use the agentic system for complex tasks
- /explain - Explain the selected code or current file
- /fix - Fix issues in the selected code or current file
- /refactor - Refactor the selected code or current file
- /test - Generate tests for the selected code or current file
- /doc - Generate documentation for the selected code or current file
- /help - Show this help message

Shortcuts:
- Ctrl+K - Focus command bar
- Ctrl+O - Open file
- Ctrl+S - Save file
- Ctrl+Q - Quit
- Escape - Focus editor

Tips:
- Select code before using commands for better context
- Use /run_agent for complex tasks like project analysis
- The AI can help with debugging, optimization, and more
        """
        
        # Display help command in output panel
        if hasattr(self, 'output_panel') and self.output_panel:
            self.output_panel.add_ai_response("/help", help_text.strip())
        
        self.post_message(self.CommandExecuted("/help", help_text.strip()))
    
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
        except (AttributeError, ValueError) as e:
            # Log warning synchronously since this is not an async method
            pass
        
        return context
    
    async def _handle_tool_calls(self, tool_calls: list) -> None:
        """Handle tool calls from Kimi API response."""
        for tool_call in tool_calls:
            function_name = tool_call.get('function', {}).get('name')
            arguments_str = tool_call.get('function', {}).get('arguments', '{}')
            
            try:
                # The arguments can be a string-encoded JSON object
                if isinstance(arguments_str, str):
                    arguments = json.loads(arguments_str)
                else:
                    arguments = arguments_str

                if function_name == "replace_code":
                    await self._tool_replace_code(**arguments)
                elif function_name == "write_file":
                    await self._tool_write_file(**arguments)
                elif function_name == "read_file":
                    await self._tool_read_file(**arguments)
                else:
                    # Delegate to ToolExecutor for other tools
                    if self.tool_executor:
                        result = await self.tool_executor.execute_tool(function_name, arguments)
                        
                        if result and result.get("error"):
                            await self.logger.error(f"Tool {function_name} execution failed: {result['error']}")
                        else:
                            await self.logger.info(f"Tool {function_name} executed with result: {result}")
                    else:
                        await self.logger.warning(f"Unknown tool: {function_name}")
            
            except json.JSONDecodeError as e:
                await self.logger.error(f"Failed to decode arguments for tool {function_name}: {e}", exc_info=True)
            except Exception as e:
                await self.logger.error(f"Tool execution error for {function_name}: {e}", exc_info=True)
    
    async def _tool_replace_code(self, start_line: int, end_line: int, new_code: str) -> None:
        """Tool: Replace code in the editor."""
        if self.editor:
            self.editor.replace_lines(start_line, end_line, new_code)
            await self.logger.info(f"Replaced lines {start_line}-{end_line}")
    
    async def _tool_write_file(self, path: str, content: str) -> None:
        """Tool: Write content to a file."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            await self.logger.info(f"Written to {path}")
        except Exception as e:
            await self.logger.error(f"Failed to write {path}: {e}")
    
    async def _tool_read_file(self, path: str) -> str:
        """Tool: Read content from a file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            await self.logger.info(f"Read from {path}")
            return content
        except Exception as e:
            await self.logger.error(f"Failed to read {path}: {e}")
            return ""