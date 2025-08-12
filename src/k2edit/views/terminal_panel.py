#!/usr/bin/env python3
"""Terminal panel widget for K2Edit editor."""

import asyncio
import os
import platform
import pty
import subprocess
from typing import Optional

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, RichLog
from rich.text import Text
from aiologger import Logger


class TerminalPanel(Widget):
    """A collapsible terminal panel with interactive shell support."""
    
    DEFAULT_ID = "terminal-panel"
    
    # Reactive attributes
    is_visible = reactive(False)
    height_percent = reactive(30)  # Default height as percentage of screen
    
    class ToggleVisibility(Message):
        """Message sent when terminal visibility is toggled."""
        def __init__(self, visible: bool) -> None:
            self.visible = visible
            super().__init__()
    
    def __init__(self, logger: Optional[Logger] = None, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger or Logger(name="terminal_panel")
        
        # Terminal state
        self._process: Optional[subprocess.Popen] = None
        self._master_fd: Optional[int] = None
        self._slave_fd: Optional[int] = None
        self._read_task: Optional[asyncio.Task] = None
        self._shell_command = self._get_shell_command()
        
        # UI components
        self._output_log: Optional[RichLog] = None
        self._title_bar: Optional[Static] = None
        
        # Buffer for partial output
        self._output_buffer = ""
        
    def _get_shell_command(self) -> list[str]:
        """Get the appropriate shell command for the current platform."""
        system = platform.system().lower()
        
        if system == "windows":
            # Use PowerShell on Windows
            return ["powershell.exe", "-NoLogo", "-NoExit"]
        else:
            # Use bash or zsh on Unix-like systems
            shell = os.environ.get("SHELL", "/bin/bash")
            return [shell]
    
    def compose(self) -> ComposeResult:
        """Create the terminal panel UI."""
        with Vertical(id="terminal-container"):
            # Title bar
            self._title_bar = Static("Terminal", id="terminal-title")
            yield self._title_bar
            
            # Terminal output
            self._output_log = RichLog(
                id="terminal-output",
                auto_scroll=True,
                markup=False,
                highlight=False,
                wrap=False
            )
            yield self._output_log
    
    async def on_mount(self) -> None:
        """Initialize the terminal panel."""
        await self.logger.info("Terminal panel mounted")
        
        # Initially hidden
        self.display = False
        
        # Set initial styles
        self.styles.height = "30%"
        self.styles.dock = "bottom"
        self.styles.border = ("solid", "#3b82f6")
        self.styles.background = "#1e293b"
    
    async def toggle_visibility(self) -> None:
        """Toggle terminal panel visibility."""
        self.is_visible = not self.is_visible
        
        if self.is_visible:
            await self._show_terminal()
        else:
            await self._hide_terminal()
        
        # Send message to parent
        self.post_message(self.ToggleVisibility(self.is_visible))
    
    async def _show_terminal(self) -> None:
        """Show the terminal panel and start shell if needed."""
        self.display = True
        
        if not self._process or self._process.poll() is not None:
            await self._start_shell()
        
        await self.logger.info("Terminal panel shown")
    
    async def _hide_terminal(self) -> None:
        """Hide the terminal panel."""
        self.display = False
        await self.logger.info("Terminal panel hidden")
    
    async def _start_shell(self) -> None:
        """Start the interactive shell process."""
        try:
            await self.logger.info(f"Starting shell: {' '.join(self._shell_command)}")
            
            if platform.system().lower() == "windows":
                # Windows implementation
                self._process = subprocess.Popen(
                    self._shell_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
                )
                
                # Start reading output
                self._read_task = asyncio.create_task(self._read_output_windows())
            else:
                # Unix-like systems implementation with PTY
                self._master_fd, self._slave_fd = pty.openpty()
                
                def safe_setsid():
                    """Safely set session ID, ignoring errors."""
                    try:
                        os.setsid()
                    except OSError:
                        # Ignore errors if setsid fails
                        pass
                
                self._process = subprocess.Popen(
                    self._shell_command,
                    stdin=self._slave_fd,
                    stdout=self._slave_fd,
                    stderr=self._slave_fd,
                    preexec_fn=safe_setsid,
                    start_new_session=True
                )
                
                # Close slave fd in parent process
                os.close(self._slave_fd)
                self._slave_fd = None
                
                # Start reading output
                self._read_task = asyncio.create_task(self._read_output_unix())
            
            # Add welcome message
            if self._output_log:
                welcome_text = Text(f"Shell started: {' '.join(self._shell_command)}\n", style="green")
                self._output_log.write(welcome_text)
                
        except Exception as e:
            await self.logger.error(f"Failed to start shell: {e}")
            if self._output_log:
                error_text = Text(f"Failed to start shell: {e}\n", style="red")
                self._output_log.write(error_text)
    
    async def _read_output_unix(self) -> None:
        """Read output from Unix shell using PTY."""
        try:
            while self._process and self._process.poll() is None and self._master_fd:
                try:
                    # Use asyncio to read from the master fd
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, self._read_fd_blocking, self._master_fd)
                    
                    if data:
                        await self._process_output(data)
                    else:
                        # No data, small delay to prevent busy waiting
                        await asyncio.sleep(0.01)
                        
                except (OSError, ValueError) as e:
                    await self.logger.debug(f"PTY read error (normal on close): {e}")
                    break
                except Exception as e:
                    await self.logger.error(f"Unexpected error reading PTY: {e}")
                    break
                    
        except Exception as e:
            await self.logger.error(f"Error in Unix output reader: {e}")
        finally:
            await self.logger.debug("Unix output reader finished")
    
    def _read_fd_blocking(self, fd: int) -> bytes:
        """Blocking read from file descriptor."""
        try:
            return os.read(fd, 1024)
        except (OSError, ValueError):
            return b""
    
    async def _read_output_windows(self) -> None:
        """Read output from Windows shell."""
        try:
            while self._process and self._process.poll() is None:
                try:
                    # Read with timeout
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, self._read_stdout_blocking)
                    
                    if data:
                        await self._process_output(data.encode('utf-8'))
                    else:
                        await asyncio.sleep(0.01)
                        
                except Exception as e:
                    await self.logger.error(f"Error reading Windows output: {e}")
                    break
                    
        except Exception as e:
            await self.logger.error(f"Error in Windows output reader: {e}")
        finally:
            await self.logger.debug("Windows output reader finished")
    
    def _read_stdout_blocking(self) -> str:
        """Blocking read from stdout."""
        if self._process and self._process.stdout:
            try:
                return self._process.stdout.read(1024)
            except:
                return ""
        return ""
    
    async def _process_output(self, data: bytes) -> None:
        """Process output data from shell."""
        try:
            # Decode data
            text = data.decode('utf-8', errors='replace')
            
            # Add to buffer
            self._output_buffer += text
            
            # Process complete lines
            while '\n' in self._output_buffer:
                line, self._output_buffer = self._output_buffer.split('\n', 1)
                if self._output_log:
                    self._output_log.write(line + '\n')
            
            # If buffer is getting too long without newlines, flush it
            if len(self._output_buffer) > 1000:
                if self._output_log:
                    self._output_log.write(self._output_buffer)
                self._output_buffer = ""
                
        except Exception as e:
            await self.logger.error(f"Error processing output: {e}")
    
    async def send_input(self, text: str) -> None:
        """Send input to the shell."""
        if not self._process or self._process.poll() is not None:
            await self.logger.warning("No active shell process")
            return
        
        try:
            # Ensure text ends with newline
            if not text.endswith('\n'):
                text += '\n'
            
            if platform.system().lower() == "windows":
                # Windows implementation
                if self._process.stdin:
                    self._process.stdin.write(text)
                    self._process.stdin.flush()
            else:
                # Unix implementation
                if self._master_fd:
                    os.write(self._master_fd, text.encode('utf-8'))
            
            # Echo input to output log
            if self._output_log:
                input_text = Text(text, style="cyan")
                self._output_log.write(input_text)
                
        except Exception as e:
            await self.logger.error(f"Error sending input: {e}")
    
    async def on_key(self, event: events.Key) -> None:
        """Handle key events when terminal is focused."""
        if not self.is_visible:
            return
        
        # Handle special keys
        if event.key == "ctrl+c":
            await self.send_input("\x03")  # Send Ctrl+C
            event.prevent_default()
        elif event.key == "ctrl+d":
            await self.send_input("\x04")  # Send Ctrl+D
            event.prevent_default()
        elif event.key == "enter":
            await self.send_input("\n")
            event.prevent_default()
        elif event.key == "backspace":
            await self.send_input("\x08")  # Send backspace
            event.prevent_default()
        elif len(event.key) == 1:  # Regular character
            await self.send_input(event.key)
            event.prevent_default()
    
    async def cleanup(self) -> None:
        """Clean up terminal resources."""
        await self.logger.info("Cleaning up terminal panel")
        
        # Cancel read task
        if self._read_task and not self._read_task.done():
            await self.logger.info("Cancelling terminal read task")
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, RuntimeError):
                await self.logger.info("Terminal read task cancelled or event loop closed")
                pass
        
        # Terminate process
        if self._process:
            await self.logger.info(f"Terminating terminal process {self._process.pid}")
            try:
                # First try graceful termination
                if platform.system().lower() == "windows":
                    self._process.terminate()
                else:
                    # Send SIGTERM to process group
                    try:
                        os.killpg(os.getpgid(self._process.pid), 15)
                    except (OSError, ProcessLookupError):
                        # Process group might not exist, try direct termination
                        self._process.terminate()
                
                # Wait for process to terminate with timeout
                try:
                    # Check if event loop is still running
                    loop = asyncio.get_running_loop()
                    if loop.is_closed():
                        await self.logger.warning("Event loop closed, force killing process")
                        # Event loop is closed, force terminate immediately
                        self._force_kill_process()
                    else:
                        await self.logger.info("Waiting for terminal process to terminate")
                        await asyncio.wait_for(
                            self._wait_for_process_sync(),
                            timeout=2.0  # Reduced timeout for faster shutdown
                        )
                        await self.logger.info("Terminal process terminated gracefully")
                except (asyncio.TimeoutError, RuntimeError) as e:
                    await self.logger.warning(f"Timeout or runtime error waiting for process, force killing: {e}")
                    # Force kill if it doesn't terminate gracefully or event loop is closed
                    self._force_kill_process()
                        
            except Exception as e:
                await self.logger.error(f"Error terminating process: {e}")
                # Force kill as last resort
                self._force_kill_process()
        
        # Close file descriptors
        await self.logger.info("Closing terminal file descriptors")
        self._close_file_descriptors()
        
        self._process = None
        await self.logger.info("Terminal panel cleanup complete")
    
    def _force_kill_process(self) -> None:
        """Force kill the process immediately."""
        if self._process:
            try:
                if platform.system().lower() == "windows":
                    self._process.kill()
                else:
                    try:
                        os.killpg(os.getpgid(self._process.pid), 9)
                    except (OSError, ProcessLookupError):
                        # Process group might not exist, try direct kill
                        self._process.kill()
            except (OSError, ProcessLookupError):
                # Process might already be dead
                pass
    
    def _close_file_descriptors(self) -> None:
        """Close file descriptors safely."""
        if self._master_fd:
            try:
                os.close(self._master_fd)
            except (OSError, ValueError):
                pass
            self._master_fd = None
        
        if self._slave_fd:
            try:
                os.close(self._slave_fd)
            except (OSError, ValueError):
                pass
            self._slave_fd = None
    
    async def _wait_for_process_sync(self) -> None:
        """Wait for process to terminate synchronously."""
        if self._process:
            try:
                loop = asyncio.get_running_loop()
                if not loop.is_closed():
                    await loop.run_in_executor(None, self._process.wait)
                else:
                    # Fallback to synchronous wait if loop is closed
                    self._process.wait()
            except RuntimeError:
                # Event loop is closed, use synchronous wait
                self._process.wait()
    
    async def _wait_for_process(self) -> None:
        """Wait for process to terminate (legacy method)."""
        await self._wait_for_process_sync()
    
    async def on_unmount(self) -> None:
        """Clean up when widget is unmounted."""
        await self.cleanup()