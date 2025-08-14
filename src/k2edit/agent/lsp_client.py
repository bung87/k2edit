"""Improved LSP Client with Non-blocking Concurrent Operations"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

import aiofiles
from dataclasses import dataclass
from enum import Enum
import time
from aiologger import Logger
from ..utils.language_utils import detect_language_by_extension

class ServerStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class LSPConnection:
    """Represents a connection to a language server"""
    language: str
    project_root: Path
    process: asyncio.subprocess.Process
    status: ServerStatus
    last_activity: float
    pending_requests: Dict[int, asyncio.Future]
    message_id_counter: int = 0
    failed_health_checks: int = 0
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        # A connection is healthy if:
        # 1. Status is STARTING or RUNNING (not ERROR or STOPPED)
        # 2. Process is still alive (returncode is None)
        # 3. Process object exists
        return (self.status in [ServerStatus.STARTING, ServerStatus.RUNNING] and 
                self.process is not None and
                self.process.returncode is None)
    
    def get_next_message_id(self) -> int:
        """Get next message ID for this connection"""
        self.message_id_counter += 1
        return self.message_id_counter


class LSPClient:
    """Improved LSP client with non-blocking concurrent operations"""
    
    def __init__(self, logger: Logger, diagnostics_callback: Callable = None, show_message_callback: Callable = None):
        # All logging is now standardized to async patterns
        self.logger = logger
        # Use composite key (language, project_root) for server identification
        self.connections: Dict[str, LSPConnection] = {}
        self.diagnostics: Dict[str, List[Dict[str, Any]]] = {}
        self.diagnostics_callback = diagnostics_callback
        self.show_message_callback = show_message_callback
        self.health_monitor_task: Optional[asyncio.Task] = None
        self.message_readers: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.request_timeout = 15.0  # seconds - balanced timeout for large files
        self.health_check_interval = 30.0
        self.max_failed_health_checks = 3
        self.failed_health_checks: Dict[str, int] = {}
        
        # Language-specific timeouts (some servers are slower)
        self.language_timeouts = {
            "nim": 30.0,  # Nim LSP can be slower, especially on first requests
            "rust": 25.0,  # Rust analyzer can be slow on large projects
            "go": 20.0,    # Go LSP can be slow with modules
        }
        
        # Server operation locks to prevent concurrent starts/restarts
        self._server_locks: Dict[str, asyncio.Lock] = {}
        

    
    def _get_server_key(self, language: str, project_root: Path) -> str:
        """Generate a unique key for server identification based on language and project root"""
        return f"{language}:{str(project_root)}"
    
    def _find_server_key_by_language(self, language: str) -> Optional[str]:
        """Find the first server key for a given language (for backward compatibility)"""
        for key in self.connections:
            if key.startswith(f"{language}:"):
                return key
        return None
        
    async def start_server(self, language: str, command: List[str], project_root: Path) -> bool:
        """Start a language server with improved error handling"""
        server_key = self._get_server_key(language, project_root)
        # Get or create lock for this server key
        if server_key not in self._server_locks:
            self._server_locks[server_key] = asyncio.Lock()
        
        async with self._server_locks[server_key]:
            return await self._start_server_internal(language, command, project_root)
    
    async def _start_server_internal(self, language: str, command: List[str], project_root: Path) -> bool:
        """Internal server start logic without locking"""
        try:
            server_key = self._get_server_key(language, project_root)
            await self.logger.info(f"Starting {language} language server for {project_root}: {' '.join(command)}")
            
            # Check if server is already running (another task might have started it)
            if server_key in self.connections and self.connections[server_key].is_healthy():
                await self.logger.info(f"{language} server for {project_root} is already running and healthy")
                return True
            
            # Stop existing server if running
            if server_key in self.connections:
                await self.stop_server(language, project_root)
            
            # Create subprocess with specific error handling
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(project_root)
                )
            except (FileNotFoundError, PermissionError, OSError) as e:
                error_type = type(e).__name__
                await self.logger.error(f"{error_type} starting {language} server: {e}")
                return False
            
            # Create connection object
            connection = LSPConnection(
                language=language,
                project_root=project_root,
                process=process,
                status=ServerStatus.STARTING,
                last_activity=time.time(),
                pending_requests={}
            )
            
            self.connections[server_key] = connection
            
            # Start message reader
            try:
                reader_task = asyncio.create_task(self._message_reader(server_key))
                self.message_readers[server_key] = reader_task
            except RuntimeError as e:
                await self.logger.error(f"Failed to create message reader task for {language}: {e}")
                await self.stop_server(language, project_root)
                return False
            
            # Start stderr logger
            # try:
            #     asyncio.create_task(self._stderr_logger(language))
            # except RuntimeError as e:
            #     await self.logger.warning(f"Failed to create stderr logger task for {language}: {e}")
            #     # Don't fail the entire operation for this
            
            await self.logger.info(f"{language} server started with PID: {process.pid}")
            
            # # Start health monitoring if not already running
            # if self.health_monitor_task is None:
            #     try:
            #         self.health_monitor_task = asyncio.create_task(self._health_monitor())
            #     except RuntimeError as e:
            #         await self.logger.warning(f"Failed to create health monitor task: {e}")
            #         # Don't fail the entire operation for this
            
            return True
            
        except Exception as e:
            await self.logger.error(f"Failed to start {language} server: {e}", exc_info=True)
            return False
    
    async def stop_server(self, language: str, project_root: Path = None) -> None:
        """Stop a language server gracefully"""
        # For backward compatibility, if no project_root provided, stop all servers for this language
        if project_root is None:
            servers_to_stop = [key for key in self.connections.keys() if key.startswith(f"{language}:")]
            for server_key in servers_to_stop:
                connection = self.connections[server_key]
                await self._stop_server_internal(server_key, connection)
            return
            
        server_key = self._get_server_key(language, project_root)
        if server_key not in self.connections:
            return
            
        connection = self.connections[server_key]
        await self._stop_server_internal(server_key, connection)
    
    async def _stop_server_internal(self, server_key: str, connection: LSPConnection) -> None:
        """Internal method to stop a specific server connection"""
        language = connection.language
        project_root = connection.project_root
        
        await self.logger.info(f"Stopping server for {language} in {project_root}. Process: {connection.process.pid if connection.process else 'N/A'}")
        
        # Cancel pending requests
        try:
            await self.logger.info(f"Cancelling {len(connection.pending_requests)} pending requests for {language}")
            for future in connection.pending_requests.values():
                if not future.done():
                    future.cancel()
        except Exception as e:
            await self.logger.warning(f"Error cancelling pending requests for {language}: {e}")
        
        # Stop message reader
        try:
            if server_key in self.message_readers:
                await self.logger.info(f"Stopping message reader for {language}")
                self.message_readers[server_key].cancel()
                del self.message_readers[server_key]
        except Exception as e:
            await self.logger.warning(f"Error stopping message reader for {language}: {e}")
        
        # Terminate process
        try:
            if connection.process and connection.process.returncode is None:
                await self.logger.info(f"Terminating process for {language}")
                connection.process.terminate()
                try:
                    await asyncio.wait_for(connection.process.wait(), timeout=5.0)
                    await self.logger.info(f"Process for {language} terminated gracefully.")
                except asyncio.TimeoutError:
                    await self.logger.warning(f"Timeout waiting for {language} process to terminate. Killing it.")
                    connection.process.kill()
                    await connection.process.wait()
                    await self.logger.info(f"Process for {language} killed.")
        except (ProcessLookupError, OSError) as e:
            await self.logger.warning(f"Process error stopping {language} server: {e}")
        except Exception as e:
            await self.logger.error(f"Error stopping {language} server: {e}")
        finally:
            await self.logger.info(f"Cleaning up connection for {language} in {project_root}")
            if server_key in self.connections:
                del self.connections[server_key]
            self.failed_health_checks.pop(server_key, None)
    
    async def initialize_connection(self, language: str, project_root: Path, settings: Dict[str, Any] = None) -> bool:
        """Initialize LSP connection with capabilities and settings"""
        server_key = self._get_server_key(language, project_root)
        if server_key not in self.connections:
            return False
        
        init_params = {
            "processId": None,
            "rootUri": f"file://{project_root}",
            "capabilities": {
                "textDocument": {
                    "hover": {"dynamicRegistration": True},
                    "definition": {"dynamicRegistration": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {"dynamicRegistration": True},
                    "workspaceSymbol": {"dynamicRegistration": True},
                    "completion": {"dynamicRegistration": True},
                    "publishDiagnostics": {"relatedInformation": True}
                },
                "workspace": {
                    "symbol": {"dynamicRegistration": True},
                    "workspaceFolders": True
                }
            }
        }
        
        # Add language-specific settings if provided
        if settings:
            init_params["initializationOptions"] = settings
        
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": init_params
        }
        

        # Send initialization request for other languages
        try:
            response = await self.send_request(language, init_request)
        except (ConnectionError, json.JSONDecodeError) as e:
            error_type = type(e).__name__
            await self.logger.error(f"{error_type} initializing {language} server: {e}")
            return False
        except Exception as e:
            await self.logger.error(f"Error initializing {language} server: {e}")
            return False
        
        # Handle response
        if response and "result" in response:
            # Mark connection as running
            self.connections[server_key].status = ServerStatus.RUNNING
            
            # Send initialized notification
            try:
                await self.send_notification(language, {
                    "jsonrpc": "2.0",
                    "method": "initialized",
                    "params": {}
                })
            except Exception as e:
                await self.logger.warning(f"Failed to send initialized notification for {language}: {e}")
                # Don't fail initialization for this
            
            await self.logger.info(f"{language} server initialized successfully")
            return True
        else:
            await self.logger.error(f"Failed to initialize {language} server")
            return False
    

    
    async def send_request(self, language: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send LSP request with improved response correlation"""
        server_key = self._find_server_key_by_language(language)
        if server_key is None:
            await self.logger.warning(f"No connection for language: {language}")
            return None
        
        connection = self.connections[server_key]
        
        if not connection.is_healthy():
            await self.logger.warning(f"Connection unhealthy for {language}")
            return None
        
        # Check if process is still alive before sending request
        if connection.process.returncode is not None:
            await self.logger.warning(f"LSP server process for {language} has died (exit code: {connection.process.returncode})")
            connection.status = ServerStatus.ERROR
            return None
        
        # Assign message ID
        message_id = connection.get_next_message_id()
        request["id"] = message_id
        
        # Create future for response
        response_future = asyncio.Future()
        connection.pending_requests[message_id] = response_future
        
        try:
            # Send message
            await self._send_message(connection, request)
            connection.last_activity = time.time()
        except ConnectionError as e:
            await self.logger.error(f"Connection error sending request to {language}: {e}")
            connection.pending_requests.pop(message_id, None)
            return None
        except (TypeError, ValueError) as e:
            await self.logger.error(f"JSON encode error sending request to {language}: {e}")
            connection.pending_requests.pop(message_id, None)
            return None
        except Exception as e:
            await self.logger.error(f"Error sending request to {language}: {e}")
            connection.pending_requests.pop(message_id, None)
            return None
        
        # Wait for response with language-specific timeout
        timeout = self.language_timeouts.get(language, self.request_timeout)
        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            await self.logger.warning(f"Request {message_id} timed out for {language} after {timeout}s - server may be unresponsive")
            # Mark server as potentially unhealthy after timeout
            connection.failed_health_checks += 1
            
            # Mark connection as unhealthy after timeout
            connection.status = ServerStatus.ERROR
            await self.logger.info(f"Marking {language} server as unhealthy due to timeout")
            return None
        finally:
            # Clean up pending request
            connection.pending_requests.pop(message_id, None)

    async def get_definition(self, language: str, file_path: str, line: int, character: int) -> Optional[List[Dict[str, Any]]]:
        """Send textDocument/definition request to get definition locations"""
        if language not in self.connections:
            await self.logger.warning(f"No connection for language: {language}")
            return None
        
        # Validate file_path to prevent empty path errors
        if not file_path or not file_path.strip():
            await self.logger.error(f"Invalid file_path provided for definition request: '{file_path}'")
            return None
        
        # Ensure file_path is absolute and properly formatted
        from pathlib import Path
        try:
            file_path_obj = Path(file_path).resolve()
            file_uri = f"file://{file_path_obj}"
        except (OSError, ValueError) as e:
            await self.logger.error(f"Error resolving file path '{file_path}': {e}")
            return None
        
        definition_request = {
            "jsonrpc": "2.0",
            "method": "textDocument/definition",
            "params": {
                "textDocument": {
                    "uri": file_uri
                },
                "position": {
                    "line": line,
                    "character": character
                }
            }
        }
        
        # Send definition request
        try:
            await self.logger.debug(f"Sending definition request for {file_path} at line {line}, char {character}")
            response = await self.send_request(language, definition_request)
        except ValueError as e:
            await self.logger.error(f"Invalid position for definition request: {e}")
            return None
        except ConnectionError as e:
            await self.logger.error(f"Connection error getting definition for {file_path}: {e}")
            return None
        except Exception as e:
            await self.logger.error(f"Error getting definition for {file_path}: {e}")
            return None
        
        # Handle response
        if response and "result" in response:
            result = response["result"]
            if result is None:
                await self.logger.debug("No definitions found")
                return None
            elif isinstance(result, list):
                await self.logger.debug(f"Found {len(result)} definitions")
                return result
            elif isinstance(result, dict):
                await self.logger.debug("Found 1 definition")
                return [result]
            else:
                await self.logger.warning(f"Unexpected result type: {type(result)}")
                return None
        else:
            await self.logger.warning(f"Invalid response format: {response}")
            return None
    
    async def send_notification(self, language: str, notification: Dict[str, Any]) -> None:
        """Send LSP notification (no response expected)"""
        server_key = self._find_server_key_by_language(language)
        if server_key is None:
            return
        
        connection = self.connections[server_key]
        
        if not connection.is_healthy():
            return
        
        try:
            await self._send_message(connection, notification)
            connection.last_activity = time.time()
        except ConnectionError as e:
            await self.logger.error(f"Connection error sending notification to {language}: {e}")
        except (TypeError, ValueError) as e:
            await self.logger.error(f"JSON encode error sending notification to {language}: {e}")
        except Exception as e:
            await self.logger.error(f"Error sending notification to {language}: {e}")
    
    async def _send_message(self, connection: LSPConnection, message: Dict[str, Any]) -> None:
        """Send message to language server process"""
        message_str = json.dumps(message)
        content_length = len(message_str.encode('utf-8'))
        
        header = f"Content-Length: {content_length}\r\n\r\n"
        full_message = (header + message_str).encode('utf-8')
        
        connection.process.stdin.write(full_message)
        await connection.process.stdin.drain()
    
    async def _message_reader(self, server_key: str) -> None:
        """Read and route messages concurrently"""
        if server_key not in self.connections:
            return
        
        connection = self.connections[server_key]
        language = connection.language
        await self.logger.debug(f"Started message reader for {language}")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            while connection.is_healthy():
                try:
                    message = await self._read_single_message(connection)
                    if message is None:
                        consecutive_errors += 1
                        if consecutive_errors <= 2:  # Only log first 2 attempts
                            await self.logger.debug(f"No message read for {language} (attempt {consecutive_errors})")
                        if consecutive_errors >= max_consecutive_errors:
                            await self.logger.warning(f"Too many consecutive null reads for {language}, stopping message reader")
                            break
                        # Wait a bit before retrying
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Reset error counter on successful message read
                    consecutive_errors = 0
                    connection.last_activity = time.time()
                    
                    # Route message without blocking
                    if "method" in message:
                        # Handle notification asynchronously
                        asyncio.create_task(self._handle_notification(language, message))
                    elif "id" in message:
                        # Resolve pending request
                        message_id = message["id"]
                        if message_id in connection.pending_requests:
                            future = connection.pending_requests[message_id]
                            if not future.done():
                                future.set_result(message)
                        else:
                            await self.logger.debug(f"Received response for unknown request ID {message_id} in {language}")
                    else:
                        await self.logger.warning(f"Received message without method or id in {language}: {message}")
                                
                except (ConnectionResetError, BrokenPipeError) as e:
                    consecutive_errors += 1
                    if consecutive_errors <= 2:  # Only log first 2 attempts
                        await self.logger.warning(f"Connection error in message reader for {language} (attempt {consecutive_errors}): {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        await self.logger.error(f"Too many consecutive connection errors for {language}, marking as unhealthy")
                        connection.status = ServerStatus.ERROR
                        break
                    # Wait a bit before retrying
                    await asyncio.sleep(0.1)
                    
                except json.JSONDecodeError as e:
                    consecutive_errors += 1
                    if consecutive_errors <= 2:  # Only log first 2 attempts
                        await self.logger.warning(f"JSON decode error in message reader for {language} (attempt {consecutive_errors}): {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        await self.logger.error(f"Too many consecutive JSON errors for {language}, marking as unhealthy")
                        connection.status = ServerStatus.ERROR
                        break
                    # Wait a bit before retrying
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    consecutive_errors += 1
                    await self.logger.warning(f"Unexpected error in message reader for {language} (attempt {consecutive_errors}): {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        await self.logger.error(f"Too many consecutive errors for {language}, marking as unhealthy")
                        connection.status = ServerStatus.ERROR
                        break
                    # Wait a bit before retrying
                    await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            await self.logger.info(f"Message reader cancelled for {language}")
        finally:
            await self.logger.info(f"Message reader stopped for {language}")
    
    async def _read_single_message(self, connection: LSPConnection) -> Optional[Dict[str, Any]]:
        """Read a single LSP message from the connection"""
        try:
            # Read headers
            headers = {}
            while True:
                line = await connection.process.stdout.readline()
                if not line:
                    await self.logger.debug(f"No more data available for {connection.language}")
                    return None
                
                line = line.decode('utf-8').strip()
                if not line:
                    break
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Read content
            if 'Content-Length' not in headers:
                await self.logger.warning(f"No Content-Length header found for {connection.language}: {headers}")
                return None
            
            content_length = int(headers['Content-Length'])
            await self.logger.debug(f"Reading {content_length} bytes of content for {connection.language}")
            
            # Read content with retry logic for partial reads
            content = b''
            bytes_remaining = content_length
            max_retries = 3
            retry_count = 0
            
            while bytes_remaining > 0 and retry_count < max_retries:
                chunk = await connection.process.stdout.read(bytes_remaining)
                if not chunk:
                    retry_count += 1
                    await self.logger.debug(f"Partial read attempt {retry_count} for {connection.language}, {bytes_remaining} bytes remaining")
                    await asyncio.sleep(0.1)  # Brief pause before retry
                    continue
                
                content += chunk
                bytes_remaining -= len(chunk)
                retry_count = 0  # Reset retry count on successful read
            
            if len(content) != content_length:
                await self.logger.warning(f"Incomplete message read for {connection.language}: expected {content_length}, got {len(content)}")
                return None
            
            return json.loads(content.decode('utf-8'))
            
        except UnicodeDecodeError as e:
            await self.logger.error(f"Unicode decode error reading from {connection.language} server: {e}")
            return None
        except ConnectionResetError as e:
            await self.logger.warning(f"Connection reset reading from {connection.language} server: {e}")
            return None
        except Exception as e:
            await self.logger.error(f"Error reading message: {e}")
            return None
    
    async def _handle_notification(self, language: str, notification: Dict[str, Any]) -> None:
        """Handle LSP notifications asynchronously"""
        method = notification.get("method")
        params = notification.get("params", {})
        
        if method == "textDocument/publishDiagnostics":
            await self._handle_diagnostics(params)
        elif method == "window/logMessage":
            await self._handle_log_message(language, params)
        elif method == "window/showMessage":
            await self._handle_show_message(language, params)
        # Add more notification handlers as needed
    
    async def _handle_diagnostics(self, params: Dict[str, Any]) -> None:
        """Handle diagnostics notification"""
        uri = params.get("uri", "")
        diagnostics = params.get("diagnostics", [])
        
        if uri.startswith("file://"):
            file_path = uri[7:]  # Remove file:// prefix
            self.diagnostics[file_path] = diagnostics
            
            await self.logger.debug(f"Received {len(diagnostics)} diagnostics for {file_path}")
            
            # Notify callback if available
            if self.diagnostics_callback:
                try:
                    await self.diagnostics_callback(file_path, diagnostics)
                except KeyError as e:
                    await self.logger.warning(f"Missing key in diagnostics callback: {e}")
                except ValueError as e:
                    await self.logger.warning(f"Invalid diagnostics data format in callback: {e}")
                except Exception as e:
                    await self.logger.error(f"Error in diagnostics callback: {e}")
    
    async def _handle_log_message(self, language: str, params: Dict[str, Any]) -> None:
        """Handle log message from language server"""
        message = params.get("message", "")
        message_type = params.get("type", 1)  # 1=Error, 2=Warning, 3=Info, 4=Log
        
        if message_type == 1:
            await self.logger.error(f"[{language}-lsp] {message}")
        elif message_type == 2:
            await self.logger.warning(f"[{language}-lsp] {message}")
        else:
            await self.logger.info(f"[{language}-lsp] {message}")
    
    async def notify(self, message_type: int, language: str, message: str) -> None:
        """Notify about show message with corresponding message type"""
        if self.show_message_callback:
            try:
                await self.show_message_callback(message_type, language, message)
            except Exception as e:
                await self.logger.error(f"Error in show message callback: {e}")
    
    async def _handle_show_message(self, language: str, params: Dict[str, Any]) -> None:
        """Handle show message from language server"""
        message = params.get("message", "")
        message_type = params.get("type", 1)  # 1=Error, 2=Warning, 3=Info, 4=Log
        
        # Call notify with corresponding message type
        await self.notify(message_type, language, message)
        
        if message_type == 1:
            await self.logger.error(f"[{language}-lsp] {message}")
        elif message_type == 2:
            await self.logger.warning(f"[{language}-lsp] {message}")
        else:
            await self.logger.info(f"[{language}-lsp] {message}")
    
    # async def _stderr_logger(self, language: str) -> None:
    #     """Log stderr from language server"""
    #     if language not in self.connections:
    #         return
        
    #     connection = self.connections[language]
        
    #     try:
    #         while connection.is_healthy():
    #             line = await connection.process.stderr.readline()
    #             if not line:
    #                 break
                
    #             message = line.decode('utf-8').strip()
    #             if message and not message.startswith('DEBUG'):
    #                 await self.logger.warning(f"[{language}-stderr] {message}")
                    
    #     except UnicodeDecodeError as e:
    #         await self.logger.error(f"Unicode decode error in stderr logger for {language}: {e}")
    #     except ConnectionError as e:
    #         await self.logger.warning(f"Connection error in health monitor for {language}: {e}")
    #     except Exception as e:
    #         await self.logger.error(f"Error in health monitor for {language}: {e}")
    
    # async def _health_monitor(self) -> None:
    #     """Monitor health of all language servers"""
    #     await self.logger.info("Started LSP health monitor")
        
    #     try:
    #         while True:
    #             await asyncio.sleep(self.health_check_interval)
    #             await self._check_all_servers()
    #     except asyncio.CancelledError:
    #         await self.logger.info("Health monitor cancelled")
    #     except Exception as e:
    #         await self.logger.error(f"Error in health monitor: {e}")
    
    async def _check_all_servers(self) -> None:
        """Check health of all running servers"""
        for language in list(self.connections.keys()):
            await self._check_server_health(language)
    
    async def _check_server_health(self, language: str) -> None:
        """Check health of a specific server"""
        server_key = self._find_server_key_by_language(language)
        if server_key is None:
            return
        
        connection = self.connections[server_key]
        max_failed_health_checks = 1  # Reduced to 1 for faster recovery
        
        # Check if process is still alive
        process_alive = connection.process and connection.process.returncode is None
        
        if not connection.is_healthy() or not process_alive:
            connection.failed_health_checks += 1
            if connection.failed_health_checks <= 1:  # Only log first unhealthy state
                await self.logger.warning(
                    f"Server {language} is unhealthy (status: {connection.status}, "
                    f"process alive: {process_alive}, "
                    f"failed checks: {connection.failed_health_checks}/{max_failed_health_checks})"
                )
            
            # Restart after fewer consecutive failures for faster recovery
            if connection.failed_health_checks >= max_failed_health_checks:
                await self.logger.error(f"Server {language} failed {max_failed_health_checks} consecutive health checks, marking for restart")
                connection.status = ServerStatus.ERROR
                # Don't restart here - let the indexer handle it
            return
        else:
            # Reset failed health check counter on successful check
            if connection.failed_health_checks > 0:
                await self.logger.info(f"Server {language} health recovered after {connection.failed_health_checks} failed checks")
                connection.failed_health_checks = 0
        
        # Check for activity timeout (reduced to 5 minutes for better responsiveness)
        time_since_activity = time.time() - connection.last_activity
        if time_since_activity > 300:  # 5 minutes
            await self.logger.debug(f"Server {language} inactive for {time_since_activity:.1f}s (this is normal for idle servers)")
            # Don't restart immediately, just log the info
            # The server might be idle but still healthy
    
    async def _restart_server(self, language: str, command: List[str], project_root: Path) -> bool:
        """Restart a language server with given command and project root"""
        server_key = self._get_server_key(language, project_root)
        # Get or create lock for this server key
        if server_key not in self._server_locks:
            self._server_locks[server_key] = asyncio.Lock()
        
        async with self._server_locks[server_key]:
            await self.logger.info(f"Restarting {language} server")
            
            try:
                # Stop the existing server
                await self.stop_server(language, project_root)
                
                # Wait a moment for cleanup
                await asyncio.sleep(1.0)
                
                # Start the server again (this will use the same lock, but we're already holding it)
                # So we need to call the internal start logic directly
                return await self._start_server_internal(language, command, project_root)
                
            except Exception as e:
                await self.logger.error(f"Failed to restart {language} server: {e}")
                return False
    
    async def notify_file_opened(self, file_path: str, language: str = None) -> None:
        """Notify LSP server about opened file with async file reading"""
        try:
            if language is None:
                language = detect_language_by_extension(Path(file_path).suffix)
            
            if language == "unknown" or not self.is_server_running(language):
                return
            
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return
            
            # Async file reading
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
            except FileNotFoundError as e:
                await self.logger.warning(f"File not found when notifying LSP: {e}")
                return
            except PermissionError as e:
                await self.logger.warning(f"Permission denied reading file for LSP: {e}")
                return
            except UnicodeDecodeError as e:
                await self.logger.warning(f"Unicode decode error reading file for LSP: {e}")
                return
            except Exception as e:
                await self.logger.warning(f"Failed to read file content: {e}")
                return
            
            # Send didOpen notification
            uri = f"file://{file_path_obj.absolute()}"
            notification = {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language,
                        "version": 1,
                        "text": content
                    }
                }
            }
            
            await self.send_notification(language, notification)
            await self.logger.info(f"Notified LSP about opened file: {file_path}")
            
        except ConnectionError as e:
            await self.logger.warning(f"Connection error notifying LSP about opened file: {e}")
        except Exception as e:
            await self.logger.warning(f"Failed to notify LSP about opened file: {e}")
    
    async def notify_file_changed(self, file_path: str, content: str, language: str = None) -> None:
        """Notify LSP server about file content changes"""
        try:
            if language is None:
                language = detect_language_by_extension(Path(file_path).suffix)
            
            if language == "unknown" or not self.is_server_running(language):
                return
            
            file_path_obj = Path(file_path)
            uri = f"file://{file_path_obj.absolute()}"
            
            # Send didChange notification
            notification = {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {
                        "uri": uri,
                        "version": getattr(self, '_file_versions', {}).get(file_path, 1) + 1
                    },
                    "contentChanges": [
                        {
                            "text": content
                        }
                    ]
                }
            }
            
            # Track file versions
            if not hasattr(self, '_file_versions'):
                self._file_versions = {}
            self._file_versions[file_path] = notification["params"]["textDocument"]["version"]
            
            await self.send_notification(language, notification)
            await self.logger.info(f"Notified LSP about file change: {file_path}")
            
        except ConnectionError as e:
            await self.logger.warning(f"Connection error notifying LSP about file change: {e}")
        except Exception as e:
            await self.logger.warning(f"Failed to notify LSP about file change: {e}")
    
    async def get_hover_info(self, file_path: str, line: int, character: int, language: str = None) -> Optional[Dict[str, Any]]:
        """Get hover information from LSP server"""
        try:
            # Validate line and character parameters
            if line < 0 or character < 0:
                await self.logger.warning(f"Invalid position for hover: line={line}, character={character}")
                return None

            if language is None:
                language = detect_language_by_extension(Path(file_path).suffix)
            
            if language == "unknown" or not self.is_server_running(language):
                return None
            
            # Ensure file is opened with LSP server before hover request
            await self.notify_file_opened(file_path, language)
            
            uri = f"file://{Path(file_path).absolute()}"
            
            server_key = self._find_server_key_by_language(language)
            if server_key is None:
                return None
                
            request = {
                "jsonrpc": "2.0",
                "id": self.connections[server_key].get_next_message_id(),
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": character}
                }
            }
            
            response = await self.send_request(language, request)
            
            if response and "result" in response and response["result"]:
                return response["result"]
            return None
            
        except ValueError as e:
            await self.logger.error(f"Invalid position for hover request: {e}")
            return None
        except ConnectionError as e:
            await self.logger.error(f"Connection error getting hover info: {e}")
            return None
        except Exception as e:
            await self.logger.error(f"Failed to get hover info: {e}")
            return None

    async def get_completions(self, file_path: str, line: int, character: int, language: str = None) -> Optional[List[Dict[str, Any]]]:
        """Get completion suggestions from LSP server"""
        try:
            # Validate line and character parameters
            if line < 0 or character < 0:
                await self.logger.warning(f"Invalid position for completions: line={line}, character={character}")
                return None
                
            if language is None:
                language = detect_language_by_extension(Path(file_path).suffix)
            
            if language == "unknown" or not self.is_server_running(language):
                return None
            
            uri = f"file://{Path(file_path).absolute()}"
            
            request = {
                "jsonrpc": "2.0",
                "method": "textDocument/completion",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": character},
                    "context": {
                        "triggerKind": 1  # Invoked manually
                    }
                }
            }
            
            response = await self.send_request(language, request)
            
            if response and "result" in response:
                result = response["result"]
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict) and "items" in result:
                    return result["items"]
                elif isinstance(result, dict):
                    return [result]
            return []
            
        except ValueError as e:
            await self.logger.error(f"Invalid position for completions request: {e}")
            return None
        except ConnectionError as e:
            await self.logger.error(f"Connection error getting completions: {e}")
            return None
        except Exception as e:
            await self.logger.error(f"Failed to get completions: {e}")
            return None
    
    async def send_request_with_timeout(self, language: str, request: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
        """Send LSP request with custom timeout"""
        server_key = self._find_server_key_by_language(language)
        if server_key is None:
            await self.logger.warning(f"No connection for language: {language}")
            return None
        
        connection = self.connections[server_key]
        
        if not connection.is_healthy():
            await self.logger.warning(f"Connection unhealthy for {language}")
            return None
        
        # Check if process is still alive before sending request
        if connection.process.returncode is not None:
            await self.logger.warning(f"LSP server process for {language} has died (exit code: {connection.process.returncode})")
            connection.status = ServerStatus.ERROR
            return None
        
        # Assign message ID
        message_id = connection.get_next_message_id()
        request["id"] = message_id
        
        # Create future for response
        response_future = asyncio.Future()
        connection.pending_requests[message_id] = response_future
        
        try:
            # Send message
            await self._send_message(connection, request)
            connection.last_activity = time.time()
        except ConnectionError as e:
            await self.logger.error(f"Connection error sending request to {language}: {e}")
            connection.pending_requests.pop(message_id, None)
            return None
        except (TypeError, ValueError) as e:
            await self.logger.error(f"JSON encode error sending request to {language}: {e}")
            connection.pending_requests.pop(message_id, None)
            return None
        except Exception as e:
            await self.logger.error(f"Error sending request to {language}: {e}")
            connection.pending_requests.pop(message_id, None)
            return None
        
        # Wait for response with custom timeout
        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            await self.logger.warning(f"Request {message_id} timed out for {language} after {timeout}s - server may be unresponsive")
            # Mark server as potentially unhealthy after timeout
            connection.failed_health_checks += 1
            
            # Mark connection as unhealthy after timeout
            connection.status = ServerStatus.ERROR
            await self.logger.info(f"Marking {language} server as unhealthy due to timeout")
            return None
        finally:
            # Clean up pending request
            connection.pending_requests.pop(message_id, None)

    async def get_document_symbols(self, file_path: str, language: str = None) -> Optional[List[Dict[str, Any]]]:
        """Get document symbols for a file"""
        try:
            if language is None:
                language = detect_language_by_extension(Path(file_path).suffix)
            
            if language == "unknown":
                await self.logger.warning(f"Unknown language for file: {file_path}")
                return None
                
            if not self.is_server_running(language):
                await self.logger.warning(f"LSP server not running for language: {language}")
                return None
            
            # Ensure file is opened first
            await self.notify_file_opened(file_path, language)
            
            # Give the server a moment to process the file
            await asyncio.sleep(0.5)
            
            uri = f"file://{Path(file_path).absolute()}"
            
            request = {
                "jsonrpc": "2.0",
                "method": "textDocument/documentSymbol",
                "params": {
                    "textDocument": {"uri": uri}
                }
            }
            
            await self.logger.debug(f"Requesting document symbols for {file_path} (language: {language})")
            # Use increased timeout for large files
            response = await self.send_request_with_timeout(language, request, timeout=20.0)
            
            if response and "result" in response:
                result = response["result"]
                if isinstance(result, list):
                    await self.logger.debug(f"Found {len(result)} symbols for {file_path}")
                    return result
                else:
                    await self.logger.warning(f"Unexpected result type: {type(result)} for {file_path}")
            elif response and "error" in response:
                await self.logger.error(f"LSP error getting symbols: {response['error']}")
            else:
                await self.logger.warning(f"No response or result for document symbols: {file_path}")
                
            return []
            
        except ConnectionError as e:
            await self.logger.error(f"Connection error getting document symbols: {e}")
            return None
        except Exception as e:
            await self.logger.error(f"Failed to get document symbols: {e}")
            return None
    
    def is_server_running(self, language: str, project_root: Path = None) -> bool:
        """Check if a language server is running for the given language and project"""
        if project_root is None:
            # Backward compatibility: check if any server for this language exists
            for key in self.connections:
                if key.startswith(f"{language}:"):
                    return self.connections[key].is_healthy()
            return False
        
        server_key = self._get_server_key(language, project_root)
        return (server_key in self.connections and 
                self.connections[server_key].is_healthy())
    
    async def shutdown(self) -> None:
        """Shutdown all language servers"""
        await self.logger.info("Shutting down all LSP servers")
        
        # Cancel health monitor
        # if self.health_monitor_task:
        #     await self.logger.info("Cancelling LSP health monitor")
        #     self.health_monitor_task.cancel()
        #     try:
        #         # Only await if it's actually an asyncio task
        #         if hasattr(self.health_monitor_task, '__await__'):
        #             await self.health_monitor_task
        #     except asyncio.CancelledError:
        #         await self.logger.info("LSP health monitor cancelled")
        #         pass
        
        # Stop all servers
        for language in list(self.connections.keys()):
            await self.logger.info(f"Stopping server for language: {language}")
            await self.stop_server(language)
            await self.logger.info(f"Server for {language} stopped")
        
        await self.logger.info("All LSP servers shut down")
    
    async def shutdown_all_servers(self) -> None:
        """Alias for shutdown method for backward compatibility"""
        await self.shutdown()
    
    def get_diagnostics(self, file_path: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get diagnostics for a specific file or all files"""
        if file_path:
            return {file_path: self.diagnostics.get(file_path, [])}
        return self.diagnostics.copy()
    
    def get_server_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all language servers"""
        stats = {}
        for language, connection in self.connections.items():
            stats[language] = {
                "status": connection.status.value,
                "pid": connection.process.pid if connection.process else None,
                "pending_requests": len(connection.pending_requests),
                "last_activity": connection.last_activity,
                "failed_health_checks": self.failed_health_checks.get(language, 0)
            }
        return stats