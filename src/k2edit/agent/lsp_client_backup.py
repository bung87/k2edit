"""
LSP Client for K2Edit Agentic System
Handles low-level Language Server Protocol communication
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path
import subprocess
from aiologger import Logger


class LSPClient:
    """Low-level LSP client for communication with language servers"""
    
    def __init__(self, logger: Logger = None, diagnostics_callback=None):
        self.logger = logger or Logger(name="k2edit-lsp")
        self.processes = {}
        self.response_queues = {}
        self.message_ids = {}
        self.reader_locks = {}
        self.diagnostics: Dict[str, List[Dict[str, Any]]] = {}
        self.diagnostics_callback = diagnostics_callback
        
    async def start_server(self, language: str, command: List[str], project_root: Path) -> bool:
        """Start a language server process"""
        try:
            await self.logger.info(f"Starting {language} language server with command: {' '.join(command)}")
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(project_root)
            )
            
            self.processes[language] = process
            self.response_queues[language] = asyncio.Queue()
            self.message_ids[language] = 0
            self.reader_locks[language] = asyncio.Lock()
            
            await self.logger.info(f"{language} language server started with PID: {process.pid}")
            
            # Start message reader and stderr logger
            asyncio.create_task(self._read_lsp_messages(language))
            asyncio.create_task(self._log_stderr(language, process.stderr))
            
            return True
            
        except Exception as e:
            await self.logger.error(f"Failed to start {language} language server: {e}", exc_info=True)
            return False
    
    async def stop_server(self, language: str):
        """Stop a language server process"""
        if language in self.processes:
            process = self.processes[language]
            try:
                process.terminate()
                await process.wait()
                await self.logger.info(f"Stopped {language} language server")
            except Exception as e:
                await self.logger.error(f"Error stopping {language} language server: {e}")
            finally:
                del self.processes[language]
                if language in self.response_queues:
                    del self.response_queues[language]
    
    async def initialize_connection(self, language: str, project_root: Path) -> bool:
        """Initialize LSP connection with capabilities"""
        if language not in self.processes:
            return False
            
        init_request = {
            "jsonrpc": "2.0",
            "id": self._get_next_message_id(language),
            "method": "initialize",
            "params": {
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
        }
        
        return await self.send_request(language, init_request) is not None
    
    async def send_request(self, language: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send LSP request and wait for response"""
        if language not in self.processes:
            return None
            
        try:
            message_id = request.get("id", self._get_next_message_id(language))
            request["id"] = message_id
            
            await self._send_lsp_message(language, request)
            response = await self._read_lsp_response(language, message_id)
            
            return response
            
        except Exception as e:
            await self.logger.error(f"Failed to send LSP request: {e}")
            return None
    
    async def send_notification(self, language: str, notification: Dict[str, Any]):
        """Send LSP notification (no response expected)"""
        if language not in self.processes:
            return
            
        try:
            await self._send_lsp_message(language, notification)
        except Exception as e:
            await self.logger.error(f"Failed to send LSP notification: {e}")
    
    async def _send_lsp_message(self, language: str, message: Dict[str, Any]):
        """Send message to language server"""
        process = self.processes[language]
        
        message_str = json.dumps(message)
        content_length = len(message_str.encode('utf-8'))
        
        # LSP protocol format
        header = f"Content-Length: {content_length}\r\n\r\n"
        process.stdin.write((header + message_str).encode('utf-8'))
        await process.stdin.drain()
    
    async def _read_lsp_messages(self, language: str):
        """Read all LSP messages from the language server"""
        if language not in self.processes:
            return
            
        process = self.processes[language]
        reader_lock = self.reader_locks[language]
        
        await self.logger.info(f"Started reading LSP messages from {language} language server")
        
        while True:
            try:
                async with reader_lock:
                    # Read headers
                    headers = {}
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            await self.logger.info(f"LSP process stdout closed for {language}")
                            return
                        line = line.decode('utf-8').strip()
                        if not line:
                            break
                        if ':' in line:
                            key, value = line.split(':', 1)
                            headers[key.strip()] = value.strip()
                    
                    # Read content
                    if 'Content-Length' in headers:
                        content_length = int(headers['Content-Length'])
                        content = await process.stdout.read(content_length)
                        response = json.loads(content.decode('utf-8'))
                        
                        # Handle notifications vs responses
                        if "method" in response:
                            # This is a notification (like diagnostics)
                            await self._handle_lsp_notification(language, response)
                        else:
                            # This is a response to a request
                            await self.response_queues[language].put(response)
                            
            except asyncio.CancelledError:
                await self.logger.info(f"LSP message reader cancelled for {language}")
                break
            except Exception as e:
                await self.logger.error(f"Error reading LSP messages for {language}: {e}")
                break
                
        await self.logger.info(f"Stopped reading LSP messages from {language} language server")
    
    async def _read_lsp_response(self, language: str, message_id: int) -> Optional[Dict[str, Any]]:
        """Read response from LSP server using response queue"""
        if language not in self.response_queues:
            return None
            
        response_queue = self.response_queues[language]
        
        try:
            # Wait for response with timeout
            timeout = 10  # 10 seconds timeout
            while True:
                try:
                    response = await asyncio.wait_for(response_queue.get(), timeout=timeout)
                    
                    # Check if this response matches our request ID
                    if response.get("id") == message_id:
                        return response
                    else:
                        # Put it back in the queue if it's not for us
                        await response_queue.put(response)
                        await asyncio.sleep(0.01)  # Small delay to avoid busy waiting
                        
                except asyncio.TimeoutError:
                    await self.logger.error(f"Timeout waiting for LSP response {message_id}")
                    return None
                    
        except Exception as e:
            await self.logger.error(f"Failed to read LSP response: {e}")
            return None
    
    async def _log_stderr(self, language: str, stderr):
        """Log stderr from language server process"""
        while not stderr.at_eof():
            line = await stderr.readline()
            if line:
                await self.logger.error(f"[{language}-lsp-stderr] {line.decode().strip()}")
    
    async def _handle_lsp_notification(self, language: str, notification: Dict[str, Any]):
        """Handle LSP notifications (like diagnostics)"""
        method = notification.get("method")
        params = notification.get("params", {})
        
        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri", "")
            diagnostics = params.get("diagnostics", [])
            
            # Convert URI to relative path
            if uri.startswith("file://"):
                file_path = uri[7:]  # Remove file:// prefix
                self.diagnostics[file_path] = diagnostics
                await self.logger.debug(f"Received diagnostics for {file_path}: {len(diagnostics)} items")
                
                # Notify callback if available
                if self.diagnostics_callback:
                    try:
                        await self.diagnostics_callback(file_path, diagnostics)
                    except Exception as e:
                        await self.logger.error(f"Error in diagnostics callback: {e}")
        
    def _get_next_message_id(self, language: str) -> int:
        """Get next message ID for a language"""
        if language not in self.message_ids:
            self.message_ids[language] = 0
        
        message_id = self.message_ids[language]
        self.message_ids[language] += 1
        return message_id
    
    def is_server_running(self, language: str) -> bool:
        """Check if a language server is running"""
        return language in self.processes and self.processes[language].returncode is None
    
    async def notify_file_opened(self, file_path: str, language: str = None):
        """Notify LSP server that a file has been opened"""
        try:
            # Import here to avoid circular imports
            from .language_configs import LanguageConfigs
            
            if language is None:
                language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
            
            if language == "unknown" or not self.is_server_running(language):
                return
            
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return
            
            # Read file content
            try:
                content = file_path_obj.read_text()
            except Exception as e:
                await self.logger.warning(f"Failed to read file content for LSP: {e}")
                return
            
            # Build LSP URI
            uri = f"file://{file_path_obj.absolute()}"
            
            # Send didOpen notification
            did_open_notification = {
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
            
            await self.send_notification(language, did_open_notification)
            await self.logger.info(f"Notified LSP server about opened file: {file_path}")
            
        except Exception as e:
            await self.logger.warning(f"Failed to notify LSP server about opened file: {e}")
    
    async def get_hover_info(self, file_path: str, line: int, character: int, language: str = None) -> Optional[Dict[str, Any]]:
        """Get hover information from LSP server for a specific position"""
        await self.logger.debug(f"get_hover_info: file_path={file_path}, line={line}, character={character}")
        
        # Import here to avoid circular imports
        from .language_configs import LanguageConfigs
        
        if language is None:
            language = LanguageConfigs.detect_language_by_extension(Path(file_path).suffix)
        
        await self.logger.debug(f"Detected language: {language}")
        
        if language == "unknown":
            await self.logger.debug(f"Skipping hover: language={language}")
            return None
            
        # Check if language server is running
        if not self.is_server_running(language):
            await self.logger.debug(f"Skipping hover: language={language}, server_running=False")
            return None
        
        # Build LSP URI
        uri = f"file://{Path(file_path).absolute()}"
        
        # Textual TextArea already uses 0-based indexing, so no conversion needed
        lsp_line = line
        lsp_character = character
        await self.logger.debug(f"Position (already 0-based): editor({line}, {character}) -> LSP({lsp_line}, {lsp_character})")
        
        # Request hover information
        request = {
            "jsonrpc": "2.0",
            "id": 0,  # Will be set by LSP client
            "method": "textDocument/hover",
            "params": {
                "textDocument": {
                    "uri": uri
                },
                "position": {
                    "line": lsp_line,  # LSP uses 0-based indexing
                    "character": lsp_character  # LSP uses 0-based indexing
                }
            }
        }
        
        await self.logger.debug(f"Sending LSP hover request: {request}")
        
        try:
            response = await self.send_request(language, request)
            await self.logger.debug(f"Hover response received: {response is not None}")
            
            if response and "result" in response and response["result"]:
                await self.logger.debug(f"Hover result contents: {response['result'].get('contents', 'No contents')}")
                return response["result"]
            return None
            
        except Exception as e:
            await self.logger.error(f"Failed to get hover info: {e}")
            return None
    
    async def shutdown(self):
        """Shutdown all language servers"""
        for language in list(self.processes.keys()):
            await self.stop_server(language)
    
    def get_diagnostics(self, file_path: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get diagnostics for a specific file or all files"""
        if file_path:
            return {file_path: self.diagnostics.get(file_path, [])}
        return self.diagnostics.copy()