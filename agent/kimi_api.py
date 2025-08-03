"""Kimi API integration with support for chat, agent mode, and tool calling."""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

try:
    from openai import AsyncOpenAI
    from openai import OpenAIError, RateLimitError
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
        self.last_request_time = 0
        self.min_request_interval = float(os.getenv("KIMI_REQUEST_INTERVAL", "1.0"))  # Minimum interval between requests in seconds
    
    async def chat(
        self,
        message: str,
        context: Optional[Dict] = None,
        use_tools: bool = False,
        stream: bool = False,
        temperature: float = 0.6
    ) -> Dict[str, Any]:
        """Send a chat message to Kimi API."""
        
        import uuid
        request_id = str(uuid.uuid4())[:8]
        logger = logging.getLogger("k2edit")
        logger.info(f"Kimi API chat request [{request_id}]: {message[:50]}...")
        
        if not self.api_key:
            return {"content": "Error: Kimi API key not configured. Please set KIMI_API_KEY in .env file.", "error": "API key missing"}
        
        # Rate limiting: ensure minimum interval between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        # Log detailed context information
        self._log_context_details(context, logger)
        
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
                result = await self._stream_chat(payload)
                logger.info(f"Kimi API chat completed [{request_id}]")
                return result
            else:
                result = await self._single_chat(payload)
                logger.info(f"Kimi API chat completed [{request_id}]")
                return result
        except RateLimitError as e:
            logger.error(f"Kimi API rate limit hit [{request_id}]: {str(e)}")
            raise Exception("Rate limit exceeded. Please wait a moment and try again.")
        except OpenAIError as e:
            # Handle other OpenAI errors
            error_msg = str(e)
            logger.error(f"Kimi API chat failed [{request_id}]: {error_msg}")
            raise Exception(f"API request failed: {error_msg}")
        except Exception as e:
            # Handle unexpected errors
            error_msg = str(e)
            logger.error(f"Kimi API chat failed [{request_id}]: {error_msg}")
            raise Exception(f"API error: {error_msg}")
    
    async def run_agent(
        self,
        goal: str,
        context: Optional[Dict] = None,
        max_iterations: int = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """Run Kimi in agent mode with multi-step reasoning.
        
        Args:
            goal: The goal or question for the agent
            context: Optional context dictionary with file information
            max_iterations: Maximum number of iterations (default: 10)
            progress_callback: Optional callback function for progress updates
                            Should accept (request_id, current_iteration, max_iterations, status)
        
        Returns:
            Dict containing the final response and metadata
        """
        import uuid
        request_id = str(uuid.uuid4())[:8]
        logger = logging.getLogger("k2edit")
        
        # Use configurable max_iterations, default to 10
        if max_iterations is None:
            max_iterations = int(os.getenv("KIMI_MAX_ITERATIONS", "10"))
        
        if not self.api_key:
            return {"content": "Error: Kimi API key not configured. Please set KIMI_API_KEY in .env file.", "error": "API key missing"}
        
        logger.info(f"Starting Kimi agent analysis [{request_id}] - Max iterations: {max_iterations}")
        
        # Log detailed context information
        self._log_context_details(context, logger)
        
        agent_prompt = f"""
You are an AI coding assistant with access to tools. Your goal is: {goal}

Please break this down into steps and use the available tools to accomplish the goal.
You can read files, write files, and replace code as needed.

Context:
{json.dumps(context, indent=2) if context else 'No additional context'}

Please think step by step and use tools to accomplish the goal.
When you have completed the goal, clearly state "TASK COMPLETED" in your response.
"""
        
        messages = [{"role": "user", "content": agent_prompt}]
        # Validate and truncate context if necessary
        messages = self._validate_context_length(messages, logger)
        logger.info(f"Kimi agent started [{request_id}]: {goal[:50]}...")
        
        consecutive_no_tools = 0  # Track iterations without tool calls
        
        for iteration in range(max_iterations):
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.6,
                "tools": TOOL_SCHEMAS,
                "tool_choice": "auto"
            }
            
            # Rate limiting: ensure minimum interval between requests
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)
            
            try:
                iteration_info = f"Iteration {iteration + 1}/{max_iterations} ({((iteration + 1)/max_iterations)*100:.0f}% complete)"
                logger.info(f"Kimi agent {iteration_info} [{request_id}]")
                if progress_callback:
                    progress_callback(request_id, iteration + 1, max_iterations, iteration_info)
                response = await self._single_chat(payload)
                
                # Add assistant response to conversation
                messages.append({
                    "role": "assistant",
                    "content": response.get("content", ""),
                    "tool_calls": response.get("tool_calls")
                })
                
                # Execute tool calls if present
                if response.get("tool_calls"):
                    consecutive_no_tools = 0  # Reset counter when tools are used
                    tool_results = await self._execute_tools(response["tool_calls"])
                    
                    # Add tool results to conversation
                    for tool_call, result in zip(response["tool_calls"], tool_results):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.get("id", f"call_{iteration}"),
                            "content": json.dumps(result)
                        })
                    
                    # Continue to next iteration to get AI's response to tool results
                    continue
                else:
                    consecutive_no_tools += 1
                    content = response.get("content", "").strip()
                    
                    # Check for explicit completion signal
                    if "TASK COMPLETED" in content.upper():
                        completion_msg = f"Analysis completed successfully after {iteration + 1}/{max_iterations} iterations"
                        logger.info(f"Kimi agent completed [{request_id}] - {completion_msg}")
                        response["iterations"] = iteration + 1
                        response["completion_status"] = "completed"
                        response["summary"] = completion_msg
                        return response
                    
                    # Check if this looks like a final response
                    if content and not content.lower().startswith(("i need to", "let me", "i'll", "i will", "first", "next", "now i")):
                        # This appears to be a final answer
                        completion_msg = f"Analysis completed after {iteration + 1}/{max_iterations} iterations (final response detected)"
                        logger.info(f"Kimi agent completed [{request_id}] - {completion_msg}")
                        response["iterations"] = iteration + 1
                        response["completion_status"] = "completed"
                        response["summary"] = completion_msg
                        return response
                    
                    # If we've had 2 consecutive iterations without tools, likely done
                    if consecutive_no_tools >= 2:
                        completion_msg = f"Analysis completed after {iteration + 1}/{max_iterations} iterations (no additional tools needed)"
                        logger.info(f"Kimi agent completed [{request_id}] - {completion_msg}")
                        response["iterations"] = iteration + 1
                        response["completion_status"] = "completed"
                        response["summary"] = completion_msg
                        return response
                    
                    # Continue for one more iteration
                    continue
            
            except RateLimitError as e:
                logger.error(f"Kimi agent rate limit hit [{request_id}]: {str(e)}")
                return {
                    "content": "Rate limit exceeded. Please wait a moment and try again.",
                    "error": "Rate limit exceeded"
                }
            except OpenAIError as e:
                error_msg = str(e)
                logger.error(f"Kimi agent execution failed [{request_id}]: {error_msg}")
                return {
                    "content": f"Agent execution failed: {error_msg}",
                    "error": error_msg
                }
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Kimi agent execution failed [{request_id}]: {error_msg}")
                return {
                    "content": f"Agent execution failed: {error_msg}",
                    "error": error_msg
                }
        
        completion_msg = f"Analysis reached maximum iteration limit ({max_iterations}/{max_iterations})"
        logger.info(f"Kimi agent completed [{request_id}] - {completion_msg}")
        if progress_callback:
            progress_callback(request_id, max_iterations, max_iterations, completion_msg)
        return {
            "content": f"Analysis completed after {max_iterations} iterations. The task may require additional iterations for more comprehensive analysis.",
            "iterations": max_iterations,
            "completion_status": "max_iterations_reached",
            "summary": completion_msg
        }
    
    async def _single_chat(self, payload: Dict) -> Dict[str, Any]:
        """Send a single chat request without retry logic to prevent duplicate requests."""
        logger = logging.getLogger("k2edit")
        
        # Rate limiting: ensure minimum interval between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        # Validate and truncate context if necessary
        if "messages" in payload:
            payload["messages"] = self._validate_context_length(payload["messages"], logger)
        
        try:
            logger.info(f"Making API request with {len(payload.get('messages', []))} messages")
            response = await self.client.chat.completions.create(**payload)
            self.last_request_time = time.time()
            
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
                logger.info(f"API usage: {response.usage.total_tokens} total tokens")
            
            return result
            
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded - details: {str(e)}")
            raise Exception(f"Rate limit exceeded. Please wait a moment and try again. Details: {str(e)}")
        except OpenAIError as e:
            raise Exception(f"API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")
    
    async def _single_chat_with_messages(self, messages: List[Dict]) -> Dict[str, Any]:
        """Send a single chat request with pre-validated messages."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000
        }
        return await self._single_chat(payload)
    
    async def _stream_chat(self, payload: Dict) -> Dict[str, Any]:
        """Send a streaming chat request without retry logic to prevent duplicate requests."""
        logger = logging.getLogger("k2edit")
        payload["stream"] = True
        
        # Rate limiting: ensure minimum interval between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        # Validate and truncate context if necessary
        if "messages" in payload:
            payload["messages"] = self._validate_context_length(payload["messages"], logger)
        
        try:
            logger.info(f"Making streaming API request with {len(payload.get('messages', []))} messages")
            content_parts = []
            tool_calls = []
            usage_info = None
            
            stream = await self.client.chat.completions.create(**payload)
            self.last_request_time = time.time()
            
            async for chunk in stream:
                # Skip the final [DONE] chunk
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    
                    # Handle content
                    if delta.content:
                        content_parts.append(delta.content)
                    
                    # Handle tool calls
                    if delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            if tool_call.id:  # New tool call
                                tool_calls.append(tool_call)
                            elif tool_call.function:  # Update existing tool call
                                if tool_calls:
                                    last_tool = tool_calls[-1]
                                    if last_tool.function.arguments is None:
                                        last_tool.function.arguments = tool_call.function.arguments or ""
                                    else:
                                        last_tool.function.arguments += tool_call.function.arguments or ""
                
                # Handle usage information from the last chunk
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
                logger.info(f"Streaming API usage: {usage_info['total_tokens']} total tokens")
            
            return result
            
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded in streaming - details: {str(e)}")
            raise Exception(f"Rate limit exceeded. Please wait a moment and try again. Details: {str(e)}")
        except OpenAIError as e:
            raise Exception(f"API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")
    
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
    
    def _estimate_token_count(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough estimation: 1 token ≈ 4 characters for most languages
        # This is a conservative estimate for context validation
        return len(text) // 4
    
    def _validate_context_length(self, messages: List[Dict], logger: logging.Logger) -> List[Dict]:
        """Validate and truncate context if it exceeds limits."""
        # Kimi API context limit is approximately 200K tokens
        # We'll use a conservative limit of 150K tokens to be safe
        MAX_TOKENS = 150000
        
        total_tokens = 0
        validated_messages = []
        
        # Calculate total token count
        for msg in messages:
            content = msg.get("content", "")
            tokens = self._estimate_token_count(content)
            total_tokens += tokens
        
        logger.info(f"Estimated total context tokens: {total_tokens}")
        
        if total_tokens <= MAX_TOKENS:
            logger.info("Context within limits, proceeding with full context")
            return messages
        
        logger.warning(f"Context exceeds limit ({total_tokens} > {MAX_TOKENS}), truncating...")
        
        # Keep system message and user message, truncate middle content
        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        user_msg = messages[-1] if messages and messages[-1].get("role") == "user" else None
        
        if system_msg:
            validated_messages.append(system_msg)
            remaining_tokens = MAX_TOKENS - self._estimate_token_count(system_msg.get("content", ""))
        else:
            remaining_tokens = MAX_TOKENS
        
        if user_msg:
            user_tokens = self._estimate_token_count(user_msg.get("content", ""))
            remaining_tokens -= user_tokens
        
        # Add middle messages within remaining token budget
        middle_messages = messages[1:-1] if len(messages) > 2 else []
        for msg in middle_messages:
            content = msg.get("content", "")
            tokens = self._estimate_token_count(content)
            
            if tokens <= remaining_tokens:
                validated_messages.append(msg)
                remaining_tokens -= tokens
            else:
                # Truncate this message to fit
                if remaining_tokens > 100:  # Only truncate if we have reasonable space
                    max_chars = remaining_tokens * 4  # Convert back to characters
                    truncated_content = content[:max_chars] + "\n... (truncated due to context limit)"
                    # Ensure the truncated message doesn't exceed remaining tokens
                    truncated_tokens = self._estimate_token_count(truncated_content)
                    if truncated_tokens <= remaining_tokens:
                        validated_messages.append({
                            **msg,
                            "content": truncated_content
                        })
                break
        
        if user_msg:
            validated_messages.append(user_msg)
        
        final_tokens = sum(self._estimate_token_count(msg.get("content", "")) for msg in validated_messages)
        logger.info(f"Context truncated to {final_tokens} tokens")
        
        return validated_messages
    
    def _log_context_details(self, context: Optional[Dict], logger: logging.Logger) -> None:
        """Log detailed context information for debugging."""
        if not context:
            logger.info("No context provided")
            return
        
        logger.info("=== Context Details ===")
        
        # Log basic context info
        if context.get("current_file"):
            logger.info(f"Current file: {context['current_file']}")
        
        if context.get("language"):
            logger.info(f"Language: {context['language']}")
        
        if context.get("selected_text"):
            selected_len = len(context["selected_text"])
            logger.info(f"Selected text length: {selected_len} characters")
        
        # Log file content info
        if context.get("file_content"):
            content_len = len(context["file_content"])
            logger.info(f"File content length: {content_len} characters")
        
        # Log conversation history
        if context.get("conversation_history"):
            history_len = len(context["conversation_history"])
            total_history_chars = sum(len(str(msg)) for msg in context["conversation_history"])
            logger.info(f"Conversation history: {history_len} messages, {total_history_chars} characters")
        
        # Log enhanced context from agent system
        enhanced_keys = ["semantic_context", "relevant_history", "similar_patterns", "project_symbols"]
        for key in enhanced_keys:
            if context.get(key):
                if isinstance(context[key], list):
                    logger.info(f"{key}: {len(context[key])} items")
                elif isinstance(context[key], dict):
                    logger.info(f"{key}: {len(context[key])} keys")
                else:
                    logger.info(f"{key}: {type(context[key]).__name__}")
        
        logger.info("=== End Context Details ===")
    
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
            logger = logging.getLogger("k2edit")
            logger.error(f"Failed to read file: {str(e)}")
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
            logger = logging.getLogger("k2edit")
            logger.error(f"Failed to write file: {str(e)}")
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
            except Exception as e:
                logger.warning(f"Error during KimiAPI cleanup: {e}")