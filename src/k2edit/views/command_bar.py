"""Command bar widget for handling user commands and AI interactions."""

import asyncio
import json
from typing import Optional
from aiologger import Logger

from textual import events
from textual.message import Message
from textual.widgets import Input

from ..agent.tools import ToolExecutor
from ..logger import get_logger

class CommandBar(Input):
    """Command input widget with command processing."""
    
    def __init__(self, **kwargs):
        super().__init__(
            placeholder="Type your AI query...",
            **kwargs
        )
        self.editor = None
        self.kimi_api = None
        self.agent_integration = None
        self.logger = get_logger()
        self.tool_executor = ToolExecutor(self.logger, editor_widget=self.editor)
        self.output_panel = None
        self.ai_mode = "ask"  # Default AI mode
    
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
        """Process and execute AI command based on current mode."""
        import uuid
        request_id = str(uuid.uuid4())[:8]
        await self.logger.info(f"Processing AI command [{request_id}]: {command}")
        
        # Route to appropriate AI handler based on current mode
        if self.ai_mode == "ask":
            await self._handle_kimi_query(command)
        elif self.ai_mode == "agent":
            await self._handle_run_agent(command)
        else:
            await self.logger.warning(f"Unknown AI mode: {self.ai_mode}")
            await self._handle_kimi_query(command)  # Fallback to ask mode
    
    def set_ai_mode(self, mode: str) -> None:
        """Set the AI mode for command processing."""
        self.ai_mode = mode
    

    
    async def _handle_kimi_query(self, query: str) -> None:
        """Handle general Kimi query."""
        if not query:
            await self.logger.warning("Kimi query issued without query text")
            self.app.notify("Kimi query requires query text", severity="warning")
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
    

    
    async def _handle_run_agent(self, goal: str) -> None:
        """Handle agent mode execution using the integrated agentic system."""
        import uuid
        
        if not goal:
            await self.logger.warning("Run agent command issued without goal")
            self.app.notify("Run agent command requires a goal", severity="warning")
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