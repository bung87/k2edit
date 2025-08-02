"""Kimi API integration with support for chat, agent mode, and tool calling."""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

try:
    from openai import AsyncOpenAI
    from openai import OpenAIError
except ImportError:
    raise ImportError("OpenAI library not found. Please install with: pip install openai")
from dotenv import load_dotenv

from .schema import TOOL_SCHEMAS

# Load environment variables
load_dotenv()


class KimiAPI:
    """Kimi API client with agent and tool calling support."""
    
    def __init__(self):
        self.api_key = os.getenv("KIMI_API_KEY")
        self.base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        self.model = "kimi-k2-0711-preview"
        
        if not self.api_key or self.api_key == "your_actual_api_key_here":
            print("Warning: KIMI_API_KEY not set. AI features will be disabled.")
            self.api_key = None
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60.0
        )
    
    async def chat(
        self,
        message: str,
        context: Optional[Dict] = None,
        use_tools: bool = False,
        stream: bool = False,
        temperature: float = 0.6
    ) -> Dict[str, Any]:
        """Send a chat message to Kimi API."""
        
        if not self.api_key:
            return {"content": "Error: Kimi API key not configured. Please set KIMI_API_KEY in .env file.", "error": "API key missing"}
        
        messages = self._build_messages(message, context)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        if use_tools:
            payload["tools"] = TOOL_SCHEMAS
            payload["tool_choice"] = "auto"
        
        try:
            if stream:
                return await self._stream_chat(payload)
            else:
                return await self._single_chat(payload)
        
        except OpenAIError as e:
            raise Exception(f"API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"API error: {str(e)}")
    
    async def run_agent(
        self,
        goal: str,
        context: Optional[Dict] = None,
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Run Kimi in agent mode with multi-step reasoning."""
        
        if not self.api_key:
            return {"content": "Error: Kimi API key not configured. Please set KIMI_API_KEY in .env file.", "error": "API key missing"}
        
        agent_prompt = f"""
You are an AI coding assistant with access to tools. Your goal is: {goal}

Please break this down into steps and use the available tools to accomplish the goal.
You can read files, write files, and replace code as needed.

Context:
{json.dumps(context, indent=2) if context else 'No additional context'}

Please think step by step and use tools to accomplish the goal.
"""
        
        messages = [{"role": "user", "content": agent_prompt}]
        
        for iteration in range(max_iterations):
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.6,
                "tools": TOOL_SCHEMAS,
                "tool_choice": "auto"
            }
            
            try:
                response = await self._single_chat(payload)
                
                # Add assistant response to conversation
                messages.append({
                    "role": "assistant",
                    "content": response.get("content", ""),
                    "tool_calls": response.get("tool_calls")
                })
                
                # Execute tool calls if present
                if response.get("tool_calls"):
                    tool_results = await self._execute_tools(response["tool_calls"])
                    
                    # Add tool results to conversation
                    for tool_call, result in zip(response["tool_calls"], tool_results):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.get("id", f"call_{iteration}"),
                            "content": json.dumps(result)
                        })
                    
                    # Continue the conversation to get final response
                    continue
                else:
                    # No more tool calls, return final response
                    return response
            
            except Exception as e:
                return {
                    "content": f"Agent execution failed: {str(e)}",
                    "error": str(e)
                }
        
        return {
            "content": "Agent reached maximum iterations without completion",
            "error": "Max iterations exceeded"
        }
    
    async def _single_chat(self, payload: Dict) -> Dict[str, Any]:
        """Send a single chat request."""
        response = await self.client.chat.completions.create(**payload)
        
        message = response.choices[0].message
        
        result = {
            "content": message.content or "",
            "role": message.role
        }
        
        # Handle tool calls
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in message.tool_calls
            ]
        
        # Include usage information if available
        if response.usage:
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        
        return result
    
    async def _stream_chat(self, payload: Dict) -> Dict[str, Any]:
        """Send a streaming chat request."""
        payload["stream"] = True
        
        content_parts = []
        tool_calls = []
        usage_info = None
        
        stream = await self.client.chat.completions.create(**payload)
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content_parts.append(chunk.choices[0].delta.content)
            
            if chunk.choices and chunk.choices[0].delta.tool_calls:
                tool_calls.extend(chunk.choices[0].delta.tool_calls)
            
            if hasattr(chunk, 'usage') and chunk.usage:
                usage_info = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens
                }
        
        result = {
            "content": "".join(content_parts),
            "role": "assistant"
        }
        
        if tool_calls:
            result["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in tool_calls
            ]
        
        if usage_info:
            result["usage"] = usage_info
        
        return result
    
    def _build_messages(self, message: str, context: Optional[Dict] = None) -> List[Dict]:
        """Build message list with context."""
        messages = []
        
        # Add system message with context if available
        if context:
            system_content = "You are a helpful AI coding assistant. "
            
            if context.get("current_file"):
                system_content += f"Currently editing: {context['current_file']}. "
            
            if context.get("language"):
                system_content += f"Language: {context['language']}. "
            
            if context.get("selected_text"):
                system_content += "User has selected some code. "
            
            system_content += "Use tools when appropriate to help with file operations and code modifications."
            
            messages.append({
                "role": "system",
                "content": system_content
            })
            
            # Add conversation history if available
            if context.get("conversation_history"):
                messages.extend(context["conversation_history"])
            
            # Add file content if available
            if context.get("file_content"):
                file_content = context["file_content"]
                if len(file_content) > 4000:  # Truncate very long files
                    file_content = file_content[:4000] + "\n... (truncated)"
                
                messages.append({
                    "role": "user",
                    "content": f"Current file content:\n```\n{file_content}\n```"
                })
        else:
            # Default system message when no context
            messages.append({
                "role": "system",
                "content": "You are a helpful AI coding assistant."
            })
        
        # Add the user message
        messages.append({
            "role": "user",
            "content": message
        })
        
        return messages
    
    async def _execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute tool calls locally."""
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            arguments = tool_call.get("function", {}).get("arguments", {})
            
            # Parse arguments if they're a string
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    results.append({"error": "Invalid arguments format"})
                    continue
            
            try:
                if function_name == "read_file":
                    result = await self._tool_read_file(**arguments)
                elif function_name == "write_file":
                    result = await self._tool_write_file(**arguments)
                elif function_name == "replace_code":
                    result = await self._tool_replace_code(**arguments)
                else:
                    result = {"error": f"Unknown function: {function_name}"}
                
                results.append(result)
            
            except Exception as e:
                results.append({"error": str(e)})
        
        return results
    
    async def _tool_read_file(self, path: str) -> Dict:
        """Tool implementation: Read file."""
        try:
            file_path = Path(path)
            if not file_path.exists():
                return {"error": f"File not found: {path}"}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "path": str(file_path)
            }
        
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}
    
    async def _tool_write_file(self, path: str, content: str) -> Dict:
        """Tool implementation: Write file."""
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"File written successfully: {path}",
                "path": str(file_path)
            }
        
        except Exception as e:
            return {"error": f"Failed to write file: {str(e)}"}
    
    async def _tool_replace_code(self, start_line: int, end_line: int, new_code: str) -> Dict:
        """Tool implementation: Replace code (this would be handled by the editor)."""
        return {
            "success": True,
            "message": f"Code replacement requested: lines {start_line}-{end_line}",
            "start_line": start_line,
            "end_line": end_line,
            "new_code": new_code
        }
    
    async def close(self):
        """Close the OpenAI client."""
        await self.client.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            asyncio.create_task(self.close())
        except Exception as e:
            # Log the error during cleanup, but don't prevent cleanup
            try:
                import logging
                logger = logging.getLogger("k2edit")
                logger.warning(f"Error during KimiAPI cleanup: {e}")
            except:
                pass