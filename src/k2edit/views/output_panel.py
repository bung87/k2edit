"""Output panel widget for displaying AI responses and command results."""

from textual.widgets import RichLog, Static
from textual.containers import Vertical
from textual.message import Message
from textual import events
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from datetime import datetime


class OutputPanel(Vertical):
    """Panel for displaying command outputs and AI responses."""
    
    DEFAULT_CSS = """
    OutputPanel {
        width: 25%;
        height: 100%;
        background: #0f172a;
        border-left: solid #3b82f6;
        margin: 0;
        padding: 1;
        min-width: 15;
    }
    
    OutputPanel.resize-hover {
        border-left: thick #60a5fa;
        background: #1e40af20;
    }
    
    OutputPanel #output-title {
        background: #1e293b;
        color: #f1f5f9;
        text-align: center;
        padding: 0 1;
        margin-bottom: 1;
        text-style: bold;
    }
    
    OutputPanel #output-log {
        background: #0f172a;
        color: #f1f5f9;
        border: none;
        scrollbar-background: #1e293b;
        scrollbar-color: #3b82f6;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_resizing = False
        self._is_hovering_edge = False
        self._resize_start_x = 0
        self._resize_start_width = 0
        self._min_width = 15
        self._edge_threshold = 2
    
    def compose(self):
        """Compose the output panel layout."""
        yield Static("[bold]AI Assistant[/bold]", id="output-title")
        yield RichLog(
            highlight=True,
            markup=True,
            wrap=True,
            auto_scroll=True,
            id="output-log"
        )
    
    def on_mount(self) -> None:
        """Initialize the output panel."""
        # Output panel is ready for AI responses and command results
        # Welcome message should be added explicitly when needed
        pass
    
    def add_welcome_message(self) -> None:
        """Add a welcome message to the output panel."""
        welcome_text = Text()
        welcome_text.append("AI Assistant Ready\n", style="bold blue")
        welcome_text.append("Commands: /help, /kimi <query>, /explain, /fix, /refactor\n")
        welcome_text.append("Select code and use commands for AI assistance")
        
        panel = Panel(
            welcome_text,
            title="AI Assistant",
            border_style="blue"
        )
        log = self.query_one("#output-log", RichLog)
        log.write(panel)
    
    def add_command_result(self, command: str, result: str) -> None:
        """Add a command result to the output panel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create command header
        command_header = Text()
        command_header.append(f"[{timestamp}] ", style="dim")
        command_header.append("Command: ", style="bold blue")
        command_header.append(command, style="cyan")
        
        log = self.query_one("#output-log", RichLog)
        if log:
            log.write(command_header)
            
            # Process and display result
            if result:
                self._display_content(result)
            
            # Add separator
            log.write(Text("─" * 50, style="dim"))
    
    def add_ai_response(self, query: str, response: str, streaming: bool = False) -> None:
        """Add an AI response to the output panel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create query header
        query_header = Text()
        query_header.append(f"[{timestamp}] ", style="dim")
        query_header.append("You: ", style="bold green")
        query_header.append(query, style="white")
        
        log = self.query_one("#output-log", RichLog)
        if log:
            log.write(query_header)
            
            # Create AI response header
            ai_header = Text()
            ai_header.append("Kimi: ", style="bold magenta")
            if streaming:
                ai_header.append("(streaming...)", style="dim")
            
            log.write(ai_header)
            
            # Display response content
            if response:
                self._display_content(response)
            
            # Add separator
            log.write(Text("─" * 50, style="dim"))
    
    def add_error(self, error_message: str) -> None:
        """Add an error message to the output panel."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            error_text = Text()
            error_text.append(f"[{timestamp}] ", style="dim")
            error_text.append("Error: ", style="bold red")
            error_text.append(error_message, style="red")
            
            log = self.query_one("#output-log", RichLog)
            if log:
                log.write(error_text)
        except AttributeError as e:
            # Output log widget not available
            print(f"Output panel error method unavailable: {e}")
        except Exception as e:
            # Unexpected error writing to output panel
            print(f"Unexpected error writing error to output panel: {e}")
    
    def add_info(self, info_message: str) -> None:
        """Add an info message to the output panel."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            info_text = Text()
            info_text.append(f"[{timestamp}] ", style="dim")
            info_text.append("Info: ", style="bold blue")
            info_text.append(info_message, style="blue")
            
            log = self.query_one("#output-log", RichLog)
            if log:
                log.write(info_text)
        except AttributeError as e:
            # Output log widget not available
            print(f"Output panel info method unavailable: {e}")
        except Exception as e:
            # Unexpected error writing to output panel
            print(f"Unexpected error writing info to output panel: {e}")
    
    def add_tool_execution(self, tool_name: str, arguments: dict, result: str = None) -> None:
        """Add tool execution information."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        tool_text = Text()
        tool_text.append(f"[{timestamp}] ", style="dim")
        tool_text.append("Tool: ", style="bold yellow")
        tool_text.append(f"{tool_name}(", style="yellow")
        
        # Add arguments
        arg_parts = []
        for key, value in arguments.items():
            if isinstance(value, str) and len(value) > 50:
                value = value[:47] + "..."
            arg_parts.append(f"{key}={repr(value)}")
        
        tool_text.append(", ".join(arg_parts), style="cyan")
        tool_text.append(")", style="yellow")
        
        log = self.query_one("#output-log", RichLog)
        if log:
            log.write(tool_text)
            
            if result:
                result_text = Text()
                result_text.append("Result: ", style="bold green")
                result_text.append(result, style="green")
                log.write(result_text)
    
    def _display_content(self, content: str) -> None:
        """Display content with appropriate formatting."""
        log = self.query_one("#output-log", RichLog)
        if not log:
            return
            
        # Try to detect and format code blocks
        if "```" in content:
            self._display_markdown(content)
        elif content.strip().startswith(("def ", "class ", "import ", "from ")):
            # Looks like Python code
            self._display_code(content, "python")
        elif content.strip().startswith(("function ", "const ", "let ", "var ")):
            # Looks like JavaScript
            self._display_code(content, "javascript")
        else:
            # Regular text or markdown
            self._display_markdown(content)
    
    def _display_markdown(self, content: str) -> None:
        """Display content as markdown."""
        log = self.query_one("#output-log", RichLog)
        if not log:
            return
            
        markdown = Markdown(content)
        log.write(markdown)
    
    def _display_code(self, content: str, language: str = "text") -> None:
        """Display content as syntax-highlighted code."""
        log = self.query_one("#output-log", RichLog)
        if not log:
            return
            
        syntax = Syntax(
            content,
            language,
            theme="monokai",
            line_numbers=True,
            word_wrap=True
        )
        log.write(syntax)
    
    def clear_output(self) -> None:
        """Clear the output panel."""
        log = self.query_one("#output-log", RichLog)
        log.clear()
        self.add_welcome_message()
    
    def update_streaming_response(self, content: str) -> None:
        """Update the last response with streaming content."""
        # For now, just add the content
        # In a more sophisticated implementation, we could update the last message
        self._display_content(content)
    
    def add_agent_progress(self, request_id: str, current_iteration: int, max_iterations: int = None, status: str = "processing") -> None:
        """Add agent iteration progress indicator to output panel with simple dots."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        progress_text = Text()
        progress_text.append(f"[{timestamp}] ", style="dim")
        progress_text.append("Agent: ", style="bold cyan")
        
        if status == "started":
            progress_text.append(f"Analysis started", style="cyan")
        elif status == "processing":
            dots = "." * current_iteration
            progress_text.append(f"Analyzing{dots}", style="cyan")
        elif status == "completed":
            progress_text.append(f"Analysis completed", style="green")
        elif "Analysis reached maximum iteration limit" in str(status):
            progress_text.append(f"Analysis completed (max iterations reached)", style="yellow")
        elif status == "error":
            progress_text.append(f"Analysis failed", style="red")
        else:
            # Handle custom status messages
            progress_text.append(str(status), style="cyan")
        
        log = self.query_one("#output-log", RichLog)
        if log:
            log.write(progress_text)
    
    def clear_agent_progress(self) -> None:
        """Clear agent progress indicators (placeholder for future enhancement)."""
        pass
    
    def on_command_bar_command_executed(self, message) -> None:
        """Handle command execution messages."""
        self.add_command_result(message.command, message.result)
    
    def _is_on_left_edge(self, mouse_x: int) -> bool:
        """Check if mouse is on the left edge for resizing."""
        return mouse_x <= self._edge_threshold
    
    def _update_edge_highlight(self, hovering: bool) -> None:
        """Update visual highlighting when hovering over resize edge."""
        if hovering != self._is_hovering_edge:
            self._is_hovering_edge = hovering
            if hovering:
                self.add_class("resize-hover")
            else:
                self.remove_class("resize-hover")
    
    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle mouse move events for resizing from left edge."""
        if self._is_resizing:
            # Calculate new width based on mouse movement
            # For left edge: dragging right should shrink, dragging left should expand
            delta_x = self._resize_start_x - event.x
            new_width = max(self._min_width, self._resize_start_width + delta_x)
            
            # Update widget width
            self.styles.width = new_width
        else:
            # Check if hovering over left edge
            is_on_edge = self._is_on_left_edge(event.x)
            self._update_edge_highlight(is_on_edge)
    
    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Handle mouse down events to start resizing from left edge."""
        if self._is_on_left_edge(event.x):
            self._is_resizing = True
            self._resize_start_x = event.x
            # Get current width in cells
            self._resize_start_width = self.size.width
            self.capture_mouse()
    
    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Handle mouse up events to stop resizing."""
        if self._is_resizing:
            self._is_resizing = False
            self.release_mouse()
    
    def on_leave(self, event: events.Leave) -> None:
        """Handle mouse leave events to clear hover state."""
        if not self._is_resizing:
            self._update_edge_highlight(False)