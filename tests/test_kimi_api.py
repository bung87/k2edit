import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import AsyncMock, patch, MagicMock
from src.k2edit.agent.kimi_api import KimiAPI


class TestKimiAPI:
    """Test suite for KimiAPI class."""
    
    @pytest.fixture
    def kimi_api(self):
        """Create a KimiAPI instance with mocked client and API key."""
        with patch.dict(os.environ, {'KIMI_API_KEY': 'test-key'}):
            api = KimiAPI()
            api.api_key = 'test-key'
            
            # Create mock client
            mock_client = MagicMock()
            mock_client.chat = MagicMock()
            mock_client.chat.completions = MagicMock()
            
            # Replace the actual client with our mock
            api.client = mock_client
            
            yield api
    
    def test_initialization(self, kimi_api):
        """Test KimiAPI initialization."""
        assert kimi_api.api_key == 'test-key'
        assert kimi_api.base_url == 'https://api.moonshot.cn/v1'
        assert kimi_api.model == 'kimi-k2-0711-preview'
    
    @pytest.mark.asyncio
    async def test_single_chat(self, kimi_api):
        """Test basic chat functionality."""
        # Setup mock response
        mock_message = MagicMock()
        mock_message.content = "Hello, how can I help you?"
        mock_message.role = "assistant"
        mock_message.tool_calls = None
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        
        # Create async mock for chat.completions.create
        async def mock_create(*args, **kwargs):
            return mock_response
        
        kimi_api.client.chat.completions.create = mock_create
        
        # Test the chat
        result = await kimi_api._single_chat({"model": "test", "messages": []})
        
        assert result["content"] == "Hello, how can I help you?"
        assert result["role"] == "assistant"
        assert "usage" in result
        assert result["usage"]["total_tokens"] == 15
    
    @pytest.mark.asyncio
    async def test_chat_with_tools(self, kimi_api):
        """Test chat with tool calls."""
        # Setup mock response with tool calls
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = '{"path": "test.txt"}'
        
        mock_message = MagicMock()
        mock_message.content = ""
        mock_message.role = "assistant"
        mock_message.tool_calls = [mock_tool_call]
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        
        async def mock_create(*args, **kwargs):
            return mock_response
        
        kimi_api.client.chat.completions.create = mock_create
        
        # Test single chat with tools
        result = await kimi_api._single_chat({"model": "test", "messages": [], "tools": []})
        
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["function"]["name"] == "read_file"
    
    @pytest.mark.asyncio
    async def test_tool_execution_read_file(self, kimi_api):
        """Test the read_file tool execution."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test file content")
            temp_path = f.name
        
        try:
            result = await kimi_api._tool_read_file(temp_path)
            assert result["success"] is True
            assert result["content"] == "Test file content"
            assert result["path"] == temp_path
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_tool_execution_write_file(self, kimi_api):
        """Test the write_file tool execution."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name
        os.unlink(temp_path)  # Remove the file so we can test creation
        
        try:
            result = await kimi_api._tool_write_file(temp_path, "New file content")
            assert result["success"] is True
            assert result["path"] == temp_path
            
            # Verify file was written
            with open(temp_path, 'r') as f:
                content = f.read()
            assert content == "New file content"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_tool_execution_replace_code(self, kimi_api):
        """Test the replace_code tool execution."""
        result = await kimi_api._tool_replace_code(1, 5, "def new_function():\n    pass\n")
        assert result["success"] is True
        assert result["start_line"] == 1
        assert result["end_line"] == 5
        assert result["new_code"] == "def new_function():\n    pass\n"
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, kimi_api):
        """Test API error handling."""
        try:
            from openai import OpenAIError
        except ImportError:
            OpenAIError = Exception
        
        # Setup mock to raise OpenAI error
        async def mock_create(*args, **kwargs):
            raise OpenAIError("API Error")
        
        kimi_api.client.chat.completions.create = mock_create
        
        with pytest.raises(OpenAIError):
            await kimi_api._single_chat({"model": "test", "messages": []})
    
    @pytest.mark.asyncio
    async def test_usage_info_in_single_chat(self, kimi_api):
        """Test usage information is included in single chat response."""
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_message.role = "assistant"
        mock_message.tool_calls = None
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 20
        mock_usage.completion_tokens = 10
        mock_usage.total_tokens = 30
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        
        async def mock_create(*args, **kwargs):
            return mock_response
        
        kimi_api.client.chat.completions.create = mock_create
        
        result = await kimi_api._single_chat({"model": "test", "messages": []})
        assert "usage" in result
        assert result["usage"]["prompt_tokens"] == 20
        assert result["usage"]["completion_tokens"] == 10
        assert result["usage"]["total_tokens"] == 30
    
    @pytest.mark.asyncio
    async def test_execute_tools(self, kimi_api):
        """Test tool execution system."""
        tool_calls = [{
            "id": "call_123",
            "function": {
                "name": "read_file",
                "arguments": '{"path": "test.txt"}'
            }
        }]
        
        # Mock the tool execution
        with patch.object(kimi_api, '_tool_read_file', return_value={"success": True, "content": "file content"}) as mock_tool:
            results = await kimi_api._execute_tools(tool_calls)
            
            assert len(results) == 1
            assert results[0]["success"] is True
            mock_tool.assert_called_once_with(path="test.txt")
    
    def test_build_messages(self, kimi_api):
        """Test message building with context."""
        # Test basic message
        messages = kimi_api._build_messages("Hello")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        
        # Test with context
        context = {
            "current_file": "test.py",
            "language": "python",
            "file_content": "print('hello')"
        }
        messages = kimi_api._build_messages("Hello", context)
        assert len(messages) == 3  # system, file content, user message
        assert messages[0]["role"] == "system"
        assert "test.py" in messages[0]["content"]
        assert "python" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "print('hello')" in messages[1]["content"]