import pytest
import os
from pathlib import Path
from src.k2edit.agent.kimi_api import KimiAPI


class TestKimiAPIIntegration:
    """Integration tests that make real API calls to Kimi API."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key or self.api_key == "your_actual_api_key_here":
            pytest.skip("OPENAI_API_KEY environment variable not set or invalid")
    
    @pytest.mark.asyncio
    async def test_real_single_chat(self, logger):
        """Test a real single chat request."""
        api = KimiAPI(logger)
        try:
            response = await api.chat("Hello, this is a test message. Please respond briefly.")
            
            if "error" in response:
                pytest.fail(f"API Error: {response['content']}")
            
            assert isinstance(response, dict)
            assert "content" in response
            assert isinstance(response["content"], str)
            assert len(response["content"]) > 0
            print(f"Real API response: {response['content']}")
        finally:
            await api.close()
    
    @pytest.mark.asyncio
    async def test_real_chat_with_context(self, logger):
        """Test real chat with context/history."""
        api = KimiAPI(logger)
        try:
            # Test with context by providing a message that includes history
            context = {
                "conversation_history": [
                    {"role": "user", "content": "What is Python?"},
                    {"role": "assistant", "content": "Python is a programming language."}
                ]
            }
            
            response = await api.chat("What are its main uses?", context=context)
            
            if "error" in response:
                pytest.fail(f"API Error: {response['content']}")
            
            assert isinstance(response, dict)
            assert "content" in response
            assert isinstance(response["content"], str)
            assert len(response["content"]) > 0
            print(f"Context chat response: {response['content']}")
        finally:
            await api.close()
    
    @pytest.mark.asyncio
    async def test_real_usage_info(self, logger):
        """Test that usage info is available after real chat."""
        api = KimiAPI(logger)
        try:
            response = await api.chat("Count to 3")
            
            if "error" in response:
                pytest.fail(f"API Error: {response['content']}")
            
            assert isinstance(response, dict)
            assert "usage" in response
            assert isinstance(response["usage"], dict)
            assert "prompt_tokens" in response["usage"]
            assert "completion_tokens" in response["usage"]
            assert "total_tokens" in response["usage"]
            
            print(f"Usage info: {response['usage']}")
        finally:
            await api.close()
    
    @pytest.mark.asyncio
    async def test_real_tool_usage(self, logger):
        """Test real chat with tool usage."""
        api = KimiAPI(logger)
        try:
            # Create a temporary test file
            test_file = Path("/tmp/test_kimi_integration.txt")
            test_file.write_text("Hello from integration test")
            
            response = await api.chat(
                f"Please read the file at {test_file} and tell me what it contains",
                use_tools=True
            )
            
            if "error" in response:
                pytest.fail(f"API Error: {response['content']}")
            
            assert isinstance(response, dict)
            assert "content" in response
            assert isinstance(response["content"], str)
            assert "integration" in response["content"].lower()
            print(f"Tool usage response: {response['content']}")
            
        finally:
            await api.close()
            if test_file.exists():
                test_file.unlink()
    
    @pytest.mark.asyncio
    async def test_model_info(self, logger):
        """Test that we're using the correct model."""
        api = KimiAPI(logger)
        try:
            assert api.model == "kimi-k2-0711-preview"
            print(f"Using model: {api.model}")
            print(f"Base URL: {api.base_url}")
        finally:
            await api.close()
    
    @pytest.mark.asyncio
    async def test_api_key_loaded(self, logger):
        """Test that API key is properly loaded from environment."""
        api = KimiAPI(logger)
        try:
            assert api.api_key is not None
            assert api.api_key != "your_actual_api_key_here"
            assert len(api.api_key) > 10  # Should be a real key
            print(f"API key loaded successfully (length: {len(api.api_key)})")
        finally:
            await api.close()


if __name__ == "__main__":
    # Run tests directly for manual verification
    pytest.main([__file__, "-v", "-s"])