"""Pydantic-AI agent implementation for vibenix.

This module provides the core agent functionality using pydantic-ai.
"""

import asyncio
from typing import Optional, List, Callable, Any
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from vibenix.model_config import get_model
from vibenix.ui.conversation import get_ui_adapter, Message, Actor, Usage
from vibenix.ccl_log import get_logger
import logging

logger = logging.getLogger(__name__)


class VibenixAgent:
    """Main agent for vibenix using pydantic-ai."""
    
    def __init__(self, instructions: str = None, output_type: type = None):
        """Initialize the agent with optional custom instructions and output type."""
        self.model = get_model()
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
    
    async def run_async(self, prompt: str) -> tuple[Any, Usage]:
        """Run the agent asynchronously and return response with usage."""
        try:
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
        except UnexpectedModelBehavior as e:
            if "Content field missing from Gemini response" in str(e):
                logger.warning("Gemini returned an empty response, treating as None (no improvements needed)")
                # Return None to signal no improvements
                usage = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
                return None, usage
            else:
                raise
    
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
        
        # For text output, we use regular run method to avoid streaming issues
        # We can get rid of this by switching away from text output to structured output for the updated code
        if self._output_type is None:
            result = await self.agent.run(prompt)
            
            # Get the text output
            output = result.output
            if output:
                full_response = str(output)
                # Show the complete response in the UI
                adapter.show_message(Message(Actor.MODEL, full_response))
                print(full_response)
            
            # Get usage data
            usage_data = result.usage() if hasattr(result, 'usage') else None
            usage = Usage(
                prompt_tokens=usage_data.input_tokens if usage_data else 0,
                completion_tokens=usage_data.output_tokens if usage_data else 0,
                total_tokens=usage_data.total_tokens if usage_data else 0
            )
        else:
            # For structured output, use streaming
            async with self.agent.run_stream(prompt) as result:
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
        
        return full_response, usage
    
    def run_stream(self, prompt: str) -> tuple[str, Usage]:
        """Run the agent with streaming synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.run_stream_async(prompt))
