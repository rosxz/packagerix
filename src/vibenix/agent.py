"""Pydantic-AI agent implementation for vibenix.

This module provides the core agent functionality using pydantic-ai.
"""

import asyncio
from typing import Optional, List, Callable, Any
from pydantic import BaseModel
from pydantic_ai import Agent
from vibenix.model_config import create_model
from vibenix.ui.conversation import get_ui_adapter, Message, Actor, Usage
from vibenix.ccl_log import get_logger


class VibenixAgent:
    """Main agent for vibenix using pydantic-ai."""
    
    def __init__(self, instructions: str = None, output_type: type = None):
        """Initialize the agent with optional custom instructions and output type."""
        self.model = create_model()
        default_instructions = "You are a software packaging expert who can build any project using the Nix programming language."
        
        # Only pass output_type if it's not None
        if output_type is not None:
            self.agent = Agent(
                model=self.model,
                instructions=instructions or default_instructions,
                output_type=output_type
            )
        else:
            self.agent = Agent(
                model=self.model,
                instructions=instructions or default_instructions
            )
        
        self._tools = []
        self._output_type = output_type  # Store output type for later checks
    
    def add_tool(self, func: Callable) -> None:
        """Add a tool function to the agent."""
        # Use tool_plain since our tools don't need RunContext
        self.agent.tool_plain(func)
        self._tools.append(func)
    
    async def run_async(self, prompt: str) -> tuple[str, Usage]:
        """Run the agent asynchronously and return response with usage."""
        result = await self.agent.run(prompt)
        
        # Convert pydantic-ai usage to our Usage dataclass
        usage_data = result.usage() if hasattr(result, 'usage') else None
        usage = Usage(
            prompt_tokens=usage_data.input_tokens if usage_data else 0,
            completion_tokens=usage_data.output_tokens if usage_data else 0,
            total_tokens=usage_data.total_tokens if usage_data else 0
        )
        
        # Handle both text and structured output
        output = result.output
        
        return output, usage
    
    def run(self, prompt: str) -> tuple[str, Usage]:
        """Run the agent synchronously."""
        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.run_async(prompt))
    
    async def run_stream_async(self, prompt: str) -> tuple[str, Usage]:
        """Run the agent with streaming and return complete response with usage."""
        adapter = get_ui_adapter()
        full_response = ""
        
        async with self.agent.run_stream(prompt) as result:
            # Check if this is a text response or structured output
            if self._output_type is None:
                # Text response - can use stream_text
                async for delta in result.stream_text(delta=True):
                    full_response += delta
                    # TODO: Update UI adapter to handle streaming
                    # For now, we'll just print each chunk
                    print(delta, end="", flush=True)
            else:
                # Structured output - can't use stream_text
                # Just get the result without streaming
                pass
            
            # For structured output, get the result
            if self._output_type is not None:
                output = await result.get_output()
                full_response = str(output)
                print(full_response)
            
            # Get usage data
            usage_data = result.usage() if hasattr(result, 'usage') else None
            usage = Usage(
                prompt_tokens=usage_data.input_tokens if usage_data else 0,
                completion_tokens=usage_data.output_tokens if usage_data else 0,
                total_tokens=usage_data.total_tokens if usage_data else 0
            )
        
        print()  # newline after streaming
        return full_response, usage
    
    def run_stream(self, prompt: str) -> tuple[str, Usage]:
        """Run the agent with streaming synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.run_stream_async(prompt))