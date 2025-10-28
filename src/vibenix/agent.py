"""Pydantic-AI agent implementation for vibenix.

This module provides the core agent functionality using pydantic-ai.
"""

import asyncio
from typing import Callable, Any
from pydantic_ai import Agent, UnexpectedModelBehavior
from pydantic_ai.usage import UsageLimits
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tenacity.retry import retry_base
from pydantic_ai.exceptions import UsageLimitExceeded, UnexpectedModelBehavior
from vibenix.model_config import get_model
from vibenix.ui.conversation import get_ui_adapter, Message, Actor, Usage
from vibenix.ccl_log import get_logger
from vibenix.model_config import DEFAULT_USAGE_LIMITS
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
                output_type=output_type,
            )
        else:
            self.agent = Agent(
                model=self.model,
                instructions=instructions or default_instructions,
            )
        
        self._tools = []
        self._output_type = output_type  # Store output type for later checks
    
    # Could use https://ai.pydantic.dev/durable_execution/prefect/#durable-agent for caching
    def add_tool(self, func: Callable) -> None:
        # Use tool_plain since our tools don't need RunContext
        # All tools should be sequential to avoid race conditions in file operations
        self.agent.tool_plain(func, sequential=True)
        self._tools.append(func)
    
    @retry(
      retry=retry_if_exception_type((UnexpectedModelBehavior)),
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=3, max=60)
    )
    async def run_async(self, prompt: str) -> tuple[Any, Usage]:
        """Run the agent asynchronously and return response with usage."""
        retry_state = getattr(self, '_retry_state', None)
        attempt = retry_state.attempt_number if retry_state else 1
        if attempt > 1:
            logger.warning(f"Retrying prompt, attempt {attempt}")
        
        # Reset usage limits on retry attempts (they are fresh for each agent.run())
        limits = DEFAULT_USAGE_LIMITS.copy()
        usage_limits = UsageLimits(**limits)
        result = await self.agent.run(prompt, usage_limits=usage_limits)
        
        # Convert pydantic-ai usage to our Usage dataclass
        usage_data = result.usage() if hasattr(result, 'usage') else None
        usage = Usage(
            prompt_tokens=usage_data.input_tokens if usage_data else 0,
            completion_tokens=usage_data.output_tokens if usage_data else 0,
            cache_read_tokens=usage_data.cache_read_tokens if usage_data else 0,
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
    
    @retry(
      retry=retry_if_exception_type((UnexpectedModelBehavior)),
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=3, max=60)
    )
    async def run_stream_async(self, prompt: str) -> tuple[str, Usage]:
        """Run the agent with streaming and return complete response with usage."""
        adapter = get_ui_adapter()
        retry_state = getattr(self, '_retry_state', None)
        attempt = retry_state.attempt_number if retry_state else 1
        if attempt > 1:
            logger.warning(f"Retrying prompt, attempt {attempt}")
        
        # For text output, we use regular run method to avoid streaming issues
        # We can get rid of this by switching away from text output to structured output for the updated code
        if self._output_type is None:
            # Reset usage limits on retry attempts (they are fresh for each agent.run())
            limits = DEFAULT_USAGE_LIMITS.copy()
            usage_limits = UsageLimits(**limits)
            result = await self.agent.run(prompt, usage_limits=usage_limits)
            
            # Get the text output
            output = result.output
            full_response = ""
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
                cache_read_tokens=usage_data.cache_read_tokens if usage_data else 0,
            )
            
            return full_response, usage
        else:
            # For structured output, use streaming
            # Reset usage limits on retry attempts (they are fresh for each agent.run())
            limits = DEFAULT_USAGE_LIMITS.copy()
            usage_limits = UsageLimits(**limits)
            async with self.agent.run_stream(prompt, usage_limits=usage_limits) as result:
                output = await result.get_output()
                full_response = str(output)
                print(full_response)
                
                # Get usage data
                usage_data = result.usage() if hasattr(result, 'usage') else None
                usage = Usage(
                    prompt_tokens=usage_data.input_tokens if usage_data else 0,
                    completion_tokens=usage_data.output_tokens if usage_data else 0,
                    cache_read_tokens=usage_data.cache_read_tokens if usage_data else 0,
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
