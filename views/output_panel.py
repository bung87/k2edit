"""Output panel widget for displaying AI responses and command results."""

from textual.widgets import RichLog, Static
from textual.containers import Vertical
from textual.message import Message
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from datetime import datetime


class OutputPanel(Vertical):
    """Panel for displaying command outputs and AI responses."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
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
        log.write(command_header)
        
        # Process and display result
        if result:
            self._display_content(result)
        
        # Add separator
        log = self.query_one("#output-log", RichLog)
        log.write("─" * 50, style="dim")
    
    def add_ai_response(self, query: str, response: str, streaming: bool = False) -> None:
        """Add an AI response to the output panel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create query header
        query_header = Text()
        query_header.append(f"[{timestamp}] ", style="dim")
        query_header.append("You: ", style="bold green")
        query_header.append(query, style="white")
        
        log = self.query_one("#output-log", RichLog)
        log.write(query_header)
        
        # Create AI response header
        ai_header = Text()
        ai_header.append("Kimi: ", style="bold magenta")
        if streaming:
            ai_header.append("(streaming...)", style="dim")
        
        log = self.query_one("#output-log", RichLog)
        log.write(ai_header)
        
        # Display response content
        if response:
            self._display_content(response)
        
        # Add separator
        log = self.query_one("#output-log", RichLog)
        log.write("─" * 50, style="dim")
    
    def add_error(self, error_message: str) -> None:
        """Add an error message to the output panel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        error_text = Text()
        error_text.append(f"[{timestamp}] ", style="dim")
        error_text.append("Error: ", style="bold red")
        error_text.append(error_message, style="red")
        
        log = self.query_one("#output-log", RichLog)
        log.write(error_text)
    
    def add_info(self, info_message: str) -> None:
        """Add an info message to the output panel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        info_text = Text()
        info_text.append(f"[{timestamp}] ", style="dim")
        info_text.append("Info: ", style="bold blue")
        info_text.append(info_message, style="blue")
        
        log = self.query_one("#output-log", RichLog)
        log.write(info_text)
    
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
        log.write(tool_text)
        
        if result:
            result_text = Text()
            result_text.append("Result: ", style="bold green")
            result_text.append(result, style="green")
            log = self.query_one("#output-log", RichLog)
            log.write(result_text)
    
    def _display_content(self, content: str) -> None:
        """Display content with appropriate formatting."""
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
        try:
            markdown = Markdown(content)
            log = self.query_one("#output-log", RichLog)
            log.write(markdown)
        except Exception as e:
            # Log the error before falling back
            import logging
            logger = logging.getLogger("k2edit")
            logger.warning(f"Failed to display markdown content: {e}")
            
            # Fallback to plain text
            log = self.query_one("#output-log", RichLog)
            log.write(content)
    
    def _display_code(self, content: str, language: str = "text") -> None:
        """Display content as syntax-highlighted code."""
        try:
            syntax = Syntax(
                content,
                language,
                theme="monokai",
                line_numbers=True,
                word_wrap=True
            )
            log = self.query_one("#output-log", RichLog)
            log.write(syntax)
        except Exception as e:
            # Log the error before falling back
            import logging
            logger = logging.getLogger("k2edit")
            logger.warning(f"Failed to display syntax-highlighted code: {e}")
            
            # Fallback to plain text
            log = self.query_one("#output-log", RichLog)
            log.write(content)
    
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
    
    def on_command_bar_command_executed(self, message) -> None:
        """Handle command execution messages."""
        self.add_command_result(message.command, message.result)