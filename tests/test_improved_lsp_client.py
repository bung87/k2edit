"""Simplified tests for the improved LSP client implementation"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import logging

# Configure pytest-asyncio for async tests only
pytestmark = []

# Import the improved client
try:
    from src.k2edit.agent.improved_lsp_client import ImprovedLSPClient, LSPConnection, ServerStatus
except ImportError:
    # Fallback for different import paths
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from src.k2edit.agent.improved_lsp_client import ImprovedLSPClient, LSPConnection, ServerStatus


class TestImprovedLSPClient:
    """Test suite for ImprovedLSPClient"""
    
    def create_client(self):
        """Create a test LSP client"""
        logger = logging.getLogger("test-lsp")
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = logging.StreamHandler()
            logger.addHandler(handler)
        return ImprovedLSPClient(logger=logger)
    
    def create_mock_process(self):
        """Create a mock subprocess"""
        process = Mock()
        process.pid = 12345
        process.returncode = None
        process.stdin = AsyncMock()
        process.stdout = AsyncMock()
        process.stderr = AsyncMock()
        process.terminate = Mock()
        process.kill = Mock()
        process.wait = AsyncMock()
        return process
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization"""
        client = self.create_client()
        try:
            assert client.connections == {}
            assert client.diagnostics == {}
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_start_server_success(self, mock_subprocess):
        """Test successful server startup"""
        client = self.create_client()
        mock_process = self.create_mock_process()
        mock_subprocess.return_value = mock_process
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                result = await client.start_server(
                    language="python",
                    command=["python", "-m", "pylsp"],
                    project_root=Path(temp_dir)
                )
                
                assert result is True
                assert "python" in client.connections
                assert client.connections["python"].language == "python"
                assert client.connections["python"].process == mock_process
                assert client.connections["python"].status == ServerStatus.STARTING
            finally:
                await client.shutdown()
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_start_server_failure(self, mock_subprocess):
        """Test server startup failure"""
        client = self.create_client()
        mock_subprocess.side_effect = Exception("Failed to start")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                result = await client.start_server(
                    language="python",
                    command=["invalid-command"],
                    project_root=Path(temp_dir)
                )
                
                assert result is False
                assert "python" not in client.connections
            finally:
                await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_stop_server(self):
        """Test server shutdown"""
        client = self.create_client()
        mock_process = self.create_mock_process()
        
        try:
            # Manually add a connection
            connection = LSPConnection(
                language="python",
                process=mock_process,
                status=ServerStatus.RUNNING,
                last_activity=0,
                pending_requests={}
            )
            client.connections["python"] = connection
            
            await client.stop_server("python")
            
            assert "python" not in client.connections
            mock_process.terminate.assert_called_once()
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_send_request_no_connection(self):
        """Test sending request when no connection exists"""
        client = self.create_client()
        try:
            result = await client.send_request("python", {"method": "test"})
            assert result is None
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_send_notification(self):
        """Test sending notification"""
        client = self.create_client()
        mock_process = self.create_mock_process()
        
        try:
            # Setup connection
            connection = LSPConnection(
                language="python",
                process=mock_process,
                status=ServerStatus.RUNNING,
                last_activity=0,
                pending_requests={}
            )
            client.connections["python"] = connection
            
            # Mock the send message method
            client._send_message = AsyncMock()
            
            notification = {"method": "textDocument/didOpen", "params": {}}
            await client.send_notification("python", notification)
            
            client._send_message.assert_called_once_with(connection, notification)
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_diagnostics_handling(self):
        """Test diagnostics notification handling"""
        client = self.create_client()
        diagnostics_received = []
        
        async def diagnostics_callback(file_path, diagnostics):
            diagnostics_received.append((file_path, diagnostics))
        
        client.diagnostics_callback = diagnostics_callback
        
        try:
            # Simulate diagnostics notification
            params = {
                "uri": "file:///test/file.py",
                "diagnostics": [
                    {
                        "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
                        "message": "Test error",
                        "severity": 1
                    }
                ]
            }
            
            await client._handle_diagnostics(params)
            
            assert "/test/file.py" in client.diagnostics
            assert len(client.diagnostics["/test/file.py"]) == 1
            assert len(diagnostics_received) == 1
            assert diagnostics_received[0][0] == "/test/file.py"
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_server_health_check(self):
        """Test server health checking"""
        client = self.create_client()
        mock_process = self.create_mock_process()
        
        try:
            # Setup connection
            connection = LSPConnection(
                language="python",
                process=mock_process,
                status=ServerStatus.RUNNING,
                last_activity=0,
                pending_requests={}
            )
            client.connections["python"] = connection
            
            # Test healthy server
            assert connection.is_healthy() is True
            
            # Test unhealthy server (process died)
            mock_process.returncode = 1
            assert connection.is_healthy() is False
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_is_server_running(self):
        """Test server running check"""
        client = self.create_client()
        mock_process = self.create_mock_process()
        
        try:
            # No server
            assert client.is_server_running("python") is False
            
            # Add healthy server
            connection = LSPConnection(
                language="python",
                process=mock_process,
                status=ServerStatus.RUNNING,
                last_activity=0,
                pending_requests={}
            )
            client.connections["python"] = connection
            
            assert client.is_server_running("python") is True
            
            # Server died
            mock_process.returncode = 1
            assert client.is_server_running("python") is False
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_get_diagnostics(self):
        """Test diagnostics retrieval"""
        client = self.create_client()
        
        try:
            # Add some diagnostics
            client.diagnostics = {
                "/test/file1.py": [{"message": "error1"}],
                "/test/file2.py": [{"message": "error2"}]
            }
            
            # Get all diagnostics
            all_diagnostics = client.get_diagnostics()
            assert len(all_diagnostics) == 2
            assert "/test/file1.py" in all_diagnostics
            assert "/test/file2.py" in all_diagnostics
            
            # Get specific file diagnostics
            file_diagnostics = client.get_diagnostics("/test/file1.py")
            assert len(file_diagnostics) == 1
            assert "/test/file1.py" in file_diagnostics
            assert file_diagnostics["/test/file1.py"] == [{"message": "error1"}]
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_get_server_stats(self):
        """Test server statistics"""
        client = self.create_client()
        mock_process = self.create_mock_process()
        
        try:
            # Add a connection
            connection = LSPConnection(
                language="python",
                process=mock_process,
                status=ServerStatus.RUNNING,
                last_activity=1640995200.0,
                pending_requests={1: asyncio.Future(), 2: asyncio.Future()}
            )
            client.connections["python"] = connection
            client.failed_health_checks["python"] = 1
            
            stats = client.get_server_stats()
            
            assert "python" in stats
            python_stats = stats["python"]
            assert python_stats["status"] == "running"
            assert python_stats["pid"] == 12345
            assert python_stats["pending_requests"] == 2
            assert python_stats["last_activity"] == 1640995200.0
            assert python_stats["failed_health_checks"] == 1
        finally:
            await client.shutdown()
    
    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test client shutdown"""
        client = self.create_client()
        mock_process = self.create_mock_process()
        
        # Add connections
        connection1 = LSPConnection(
            language="python",
            process=mock_process,
            status=ServerStatus.RUNNING,
            last_activity=0,
            pending_requests={}
        )
        connection2 = LSPConnection(
            language="javascript",
            process=mock_process,
            status=ServerStatus.RUNNING,
            last_activity=0,
            pending_requests={}
        )
        
        client.connections["python"] = connection1
        client.connections["javascript"] = connection2
        
        # Mock health monitor task
        mock_task = Mock()
        mock_task.cancel = Mock()
        client.health_monitor_task = mock_task
        
        await client.shutdown()
        
        # Verify all connections were stopped
        assert len(client.connections) == 0
        
        # Verify health monitor was cancelled
        mock_task.cancel.assert_called_once()


class TestLSPConnection:
    """Test suite for LSPConnection"""
    
    @pytest.mark.asyncio
    async def test_connection_creation(self):
        """Test LSPConnection creation"""
        mock_process = Mock()
        mock_process.returncode = None
        
        connection = LSPConnection(
            language="python",
            process=mock_process,
            status=ServerStatus.RUNNING,
            last_activity=1640995200.0,
            pending_requests={}
        )
        
        assert connection.language == "python"
        assert connection.process == mock_process
        assert connection.status == ServerStatus.RUNNING
        assert connection.last_activity == 1640995200.0
        assert connection.pending_requests == {}
        assert connection.message_id_counter == 0
    
    @pytest.mark.asyncio
    async def test_is_healthy(self):
        """Test health check"""
        mock_process = Mock()
        
        # Healthy connection
        mock_process.returncode = None
        connection = LSPConnection(
            language="python",
            process=mock_process,
            status=ServerStatus.RUNNING,
            last_activity=0,
            pending_requests={}
        )
        assert connection.is_healthy() is True
        
        # Unhealthy - process died
        mock_process.returncode = 1
        assert connection.is_healthy() is False
        
        # Unhealthy - wrong status
        mock_process.returncode = None
        connection.status = ServerStatus.ERROR
        assert connection.is_healthy() is False
    
    @pytest.mark.asyncio
    async def test_get_next_message_id(self):
        """Test message ID generation"""
        mock_process = Mock()
        connection = LSPConnection(
            language="python",
            process=mock_process,
            status=ServerStatus.RUNNING,
            last_activity=0,
            pending_requests={}
        )
        
        # Test sequential ID generation
        assert connection.get_next_message_id() == 1
        assert connection.get_next_message_id() == 2
        assert connection.get_next_message_id() == 3
        assert connection.message_id_counter == 3


class TestPerformance:
    """Performance tests for the improved LSP client"""
    
    @pytest.mark.asyncio
    async def test_memory_usage(self):
        """Test that connections are properly cleaned up"""
        logger = logging.getLogger("test-lsp")
        client = ImprovedLSPClient(logger=logger)
        
        try:
            # Create and destroy multiple connections
            for i in range(5):
                mock_process = Mock()
                mock_process.returncode = None
                mock_process.terminate = Mock()
                mock_process.wait = AsyncMock()
                
                connection = LSPConnection(
                    language=f"lang{i}",
                    process=mock_process,
                    status=ServerStatus.RUNNING,
                    last_activity=0,
                    pending_requests={}
                )
                client.connections[f"lang{i}"] = connection
                
                # Stop the server
                await client.stop_server(f"lang{i}")
            
            # Verify all connections were cleaned up
            assert len(client.connections) == 0
            assert len(client.failed_health_checks) == 0
        finally:
            await client.shutdown()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])