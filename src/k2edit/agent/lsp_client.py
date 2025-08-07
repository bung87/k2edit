"""Improved LSP Client with Non-blocking Concurrent Operations"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import subprocess
import logging
import aiofiles
from dataclasses import dataclass
from enum import Enum
import time
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
    process: asyncio.subprocess.Process
    status: ServerStatus
    last_activity: float
    pending_requests: Dict[int, asyncio.Future]
    message_id_counter: int = 0
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        return (self.status in [ServerStatus.STARTING, ServerStatus.RUNNING] and 
                self.process.returncode is None)
    
    def get_next_message_id(self) -> int:
        """Get next message ID for this connection"""
        self.message_id_counter += 1
        return self.message_id_counter


class LSPClient:
    """Improved LSP client with non-blocking concurrent operations"""
    
    def __init__(self, logger: logging.Logger = None, diagnostics_callback: Callable = None):
        if logger is None:
            self.logger = logging.getLogger("k2edit-lsp-improved")
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
        else:
            self.logger = logger
        self.connections: Dict[str, LSPConnection] = {}
        self.diagnostics: Dict[str, List[Dict[str, Any]]] = {}
        self.diagnostics_callback = diagnostics_callback
        self.health_monitor_task: Optional[asyncio.Task] = None
        self.message_readers: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.request_timeout = 10.0
        self.health_check_interval = 30.0
        self.max_failed_health_checks = 3
        self.failed_health_checks: Dict[str, int] = {}
        
    async def start_server(self, language: str, command: List[str], project_root: Path) -> bool:
        """Start a language server with improved error handling"""
        try:
            self.logger.info(f"Starting {language} language server: {' '.join(command)}")
            
            # Stop existing server if running
            if language in self.connections:
                await self.stop_server(language)
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(project_root)
            )
            
            connection = LSPConnection(
                language=language,
                process=process,
                status=ServerStatus.STARTING,
                last_activity=time.time(),
                pending_requests={}
            )
            
            self.connections[language] = connection
            
            # Start message reader
            reader_task = asyncio.create_task(self._message_reader(language))
            self.message_readers[language] = reader_task
            
            # Start stderr logger
            asyncio.create_task(self._stderr_logger(language))
            
            self.logger.info(f"{language} server started with PID: {process.pid}")
            
            # Start health monitoring if not already running
            if self.health_monitor_task is None:
                self.health_monitor_task = asyncio.create_task(self._health_monitor())
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start {language} server: {e}", exc_info=True)
            return False
    
    async def stop_server(self, language: str) -> None:
        """Stop a language server gracefully"""
        if language not in self.connections:
            return
            
        connection = self.connections[language]
        
        try:
            # Cancel pending requests
            for future in connection.pending_requests.values():
                if not future.done():
                    future.cancel()
            
            # Stop message reader
            if language in self.message_readers:
                self.message_readers[language].cancel()
                del self.message_readers[language]
            
            # Terminate process
            if connection.process.returncode is None:
                connection.process.terminate()
                try:
                    await asyncio.wait_for(connection.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    connection.process.kill()
                    await connection.process.wait()
            
            self.logger.info(f"Stopped {language} language server")
            
        except Exception as e:
            self.logger.error(f"Error stopping {language} server: {e}")
        finally:
            del self.connections[language]
            self.failed_health_checks.pop(language, None)
    
    async def initialize_connection(self, language: str, project_root: Path, settings: Dict[str, Any] = None) -> bool:
        """Initialize LSP connection with capabilities and settings"""
        if language not in self.connections:
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
        
        try:
            response = await self.send_request(language, init_request)
            if response and "result" in response:
                # Mark connection as running
                self.connections[language].status = ServerStatus.RUNNING
                
                # Send initialized notification
                await self.send_notification(language, {
                    "jsonrpc": "2.0",
                    "method": "initialized",
                    "params": {}
                })
                
                self.logger.info(f"{language} server initialized successfully")
                return True
            else:
                self.logger.error(f"Failed to initialize {language} server")
                return False
                
        except Exception as e:
            self.logger.error(f"Error initializing {language} server: {e}")
            return False
    
    async def send_request(self, language: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send LSP request with improved response correlation"""
        if language not in self.connections:
            self.logger.warning(f"No connection for language: {language}")
            return None
        
        connection = self.connections[language]
        
        if not connection.is_healthy():
            self.logger.warning(f"Connection unhealthy for {language}")
            return None
        
        try:
            # Assign message ID
            message_id = connection.get_next_message_id()
            request["id"] = message_id
            
            # Create future for response
            response_future = asyncio.Future()
            connection.pending_requests[message_id] = response_future
            
            # Send message
            await self._send_message(connection, request)
            connection.last_activity = time.time()
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(response_future, timeout=self.request_timeout)
                return response
            except asyncio.TimeoutError:
                self.logger.warning(f"Request {message_id} timed out for {language}")
                return None
            finally:
                # Clean up pending request
                connection.pending_requests.pop(message_id, None)
                
        except Exception as e:
            self.logger.error(f"Error sending request to {language}: {e}")
            return None
    
    async def send_notification(self, language: str, notification: Dict[str, Any]) -> None:
        """Send LSP notification (no response expected)"""
        if language not in self.connections:
            return
        
        connection = self.connections[language]
        
        if not connection.is_healthy():
            return
        
        try:
            await self._send_message(connection, notification)
            connection.last_activity = time.time()
        except Exception as e:
            self.logger.error(f"Error sending notification to {language}: {e}")
    
    async def _send_message(self, connection: LSPConnection, message: Dict[str, Any]) -> None:
        """Send message to language server process"""
        message_str = json.dumps(message)
        content_length = len(message_str.encode('utf-8'))
        
        header = f"Content-Length: {content_length}\r\n\r\n"
        full_message = (header + message_str).encode('utf-8')
        
        connection.process.stdin.write(full_message)
        await connection.process.stdin.drain()
    
    async def _message_reader(self, language: str) -> None:
        """Read and route messages concurrently"""
        if language not in self.connections:
            return
        
        connection = self.connections[language]
        self.logger.info(f"Started message reader for {language}")
        
        try:
            while connection.is_healthy():
                message = await self._read_single_message(connection)
                if message is None:
                    break
                
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
                
        except asyncio.CancelledError:
            self.logger.info(f"Message reader cancelled for {language}")
        except Exception as e:
            self.logger.error(f"Error in message reader for {language}: {e}")
            connection.status = ServerStatus.ERROR
        finally:
            self.logger.info(f"Message reader stopped for {language}")
    
    async def _read_single_message(self, connection: LSPConnection) -> Optional[Dict[str, Any]]:
        """Read a single LSP message from the connection"""
        try:
            # Read headers
            headers = {}
            while True:
                line = await connection.process.stdout.readline()
                if not line:
                    return None
                
                line = line.decode('utf-8').strip()
                if not line:
                    break
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Read content
            if 'Content-Length' not in headers:
                return None
            
            content_length = int(headers['Content-Length'])
            content = await connection.process.stdout.read(content_length)
            
            if len(content) != content_length:
                self.logger.warning(f"Incomplete message read for {connection.language}")
                return None
            
            return json.loads(content.decode('utf-8'))
            
        except Exception as e:
            self.logger.error(f"Error reading message: {e}")
            return None
    
    async def _handle_notification(self, language: str, notification: Dict[str, Any]) -> None:
        """Handle LSP notifications asynchronously"""
        method = notification.get("method")
        params = notification.get("params", {})
        
        if method == "textDocument/publishDiagnostics":
            await self._handle_diagnostics(params)
        elif method == "window/logMessage":
            await self._handle_log_message(language, params)
        # Add more notification handlers as needed
    
    async def _handle_diagnostics(self, params: Dict[str, Any]) -> None:
        """Handle diagnostics notification"""
        uri = params.get("uri", "")
        diagnostics = params.get("diagnostics", [])
        
        if uri.startswith("file://"):
            file_path = uri[7:]  # Remove file:// prefix
            self.diagnostics[file_path] = diagnostics
            
            self.logger.debug(f"Received {len(diagnostics)} diagnostics for {file_path}")
            
            # Notify callback if available
            if self.diagnostics_callback:
                try:
                    await self.diagnostics_callback(file_path, diagnostics)
                except Exception as e:
                    self.logger.error(f"Error in diagnostics callback: {e}")
    
    async def _handle_log_message(self, language: str, params: Dict[str, Any]) -> None:
        """Handle log message from language server"""
        message = params.get("message", "")
        message_type = params.get("type", 1)  # 1=Error, 2=Warning, 3=Info, 4=Log
        
        if message_type == 1:
            self.logger.error(f"[{language}-lsp] {message}")
        elif message_type == 2:
            self.logger.warning(f"[{language}-lsp] {message}")
        else:
            self.logger.info(f"[{language}-lsp] {message}")
    
    async def _stderr_logger(self, language: str) -> None:
        """Log stderr from language server"""
        if language not in self.connections:
            return
        
        connection = self.connections[language]
        
        try:
            while connection.is_healthy():
                line = await connection.process.stderr.readline()
                if not line:
                    break
                
                message = line.decode('utf-8').strip()
                if message:
                    self.logger.warning(f"[{language}-stderr] {message}")
                    
        except Exception as e:
            self.logger.error(f"Error reading stderr for {language}: {e}")
    
    async def _health_monitor(self) -> None:
        """Monitor health of all language servers"""
        self.logger.info("Started LSP health monitor")
        
        try:
            while True:
                await asyncio.sleep(self.health_check_interval)
                await self._check_all_servers()
        except asyncio.CancelledError:
            self.logger.info("Health monitor cancelled")
        except Exception as e:
            self.logger.error(f"Error in health monitor: {e}")
    
    async def _check_all_servers(self) -> None:
        """Check health of all running servers"""
        for language in list(self.connections.keys()):
            await self._check_server_health(language)
    
    async def _check_server_health(self, language: str) -> None:
        """Check health of a specific server"""
        if language not in self.connections:
            return
        
        connection = self.connections[language]
        
        # Check if process is still alive
        if not connection.is_healthy():
            self.logger.warning(f"Server {language} is unhealthy, attempting restart")
            await self._restart_server(language)
            return
        
        # Check for activity timeout
        time_since_activity = time.time() - connection.last_activity
        if time_since_activity > 300:  # 5 minutes
            self.logger.warning(f"Server {language} inactive for {time_since_activity:.1f}s")
    
    async def _restart_server(self, language: str) -> None:
        """Restart a language server"""
        self.logger.info(f"Restarting {language} server")
        
        # This would need to be implemented with access to the original command and project_root
        # For now, just stop the server - the application layer should handle restart
        await self.stop_server(language)
    
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
            except Exception as e:
                self.logger.warning(f"Failed to read file content: {e}")
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
            self.logger.info(f"Notified LSP about opened file: {file_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to notify LSP about opened file: {e}")
    
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
            self.logger.info(f"Notified LSP about file change: {file_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to notify LSP about file change: {e}")
    
    async def get_hover_info(self, file_path: str, line: int, character: int, language: str = None) -> Optional[Dict[str, Any]]:
        """Get hover information from LSP server"""
        try:

            if language is None:
                language = detect_language_by_extension(Path(file_path).suffix)
            
            if language == "unknown" or not self.is_server_running(language):
                return None
            
            uri = f"file://{Path(file_path).absolute()}"
            
            request = {
                "jsonrpc": "2.0",
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
            
        except Exception as e:
            self.logger.error(f"Failed to get hover info: {e}")
            return None
    
    def is_server_running(self, language: str) -> bool:
        """Check if a language server is running"""
        return (language in self.connections and 
                self.connections[language].is_healthy())
    
    async def shutdown(self) -> None:
        """Shutdown all language servers"""
        self.logger.info("Shutting down all LSP servers")
        
        # Cancel health monitor
        if self.health_monitor_task:
            self.health_monitor_task.cancel()
            try:
                # Only await if it's actually an asyncio task
                if hasattr(self.health_monitor_task, '__await__'):
                    await self.health_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop all servers
        for language in list(self.connections.keys()):
            await self.stop_server(language)
        
        self.logger.info("All LSP servers shut down")
    
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