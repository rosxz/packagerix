"""Pydantic-AI agent implementation for vibenix.

This module provides the core agent functionality using pydantic-ai.
"""

import asyncio
from typing import Callable, Any
from pydantic_ai import Agent, UnexpectedModelBehavior, capture_run_messages
from pydantic_ai.usage import UsageLimits
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError
from pydantic_ai.exceptions import UsageLimitExceeded, UnexpectedModelBehavior
from vibenix.model_config import get_model
from vibenix.ui.conversation import get_ui_adapter, Message, Actor, Usage
from vibenix.ccl_log import get_logger
from vibenix.model_config import DEFAULT_USAGE_LIMITS
import logging

logger = logging.getLogger(__name__)

# Global variable to store failed messages for retry callback
_global_failed_messages = None


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
      retry=retry_if_exception_type((UsageLimitExceeded, UnexpectedModelBehavior)),
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=3, max=60),
      before_sleep=lambda retry_state: _capture_failed_usage_before_retry(retry_state, _global_failed_messages)
    )
    async def run_async(self, prompt: str) -> tuple[Any, Usage]:
        """Run the agent asynchronously and return response with usage."""
        global _global_failed_messages
        
        # Reset usage limits on retry attempts (they are fresh for each agent.run())
        limits = DEFAULT_USAGE_LIMITS.copy()
        usage_limits = UsageLimits(**limits)
        
        # Capture messages to calculate usage on failure
        with capture_run_messages() as messages:
            try:
                result = await self.agent.run(prompt, usage_limits=usage_limits)
            except (UsageLimitExceeded, UnexpectedModelBehavior) as e:
                # Store messages globally for the before_sleep callback
                _global_failed_messages = list(messages)
                logger.exception(f"Agent run failed: {type(e).__name__}")
                adapter = get_ui_adapter()
                adapter.show_error(f"{type(e).__name__}: {str(e)}")
                raise
        
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
        
        try:
            return loop.run_until_complete(self.run_async(prompt))
        except Exception as e:
            logger.exception(f"Agent run (sync) failed: {type(e).__name__}")
            adapter = get_ui_adapter()
            adapter.show_error(f"{type(e).__name__}: {str(e)}")
            raise
    
    @retry(
      retry=retry_if_exception_type((UsageLimitExceeded, UnexpectedModelBehavior)),
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=3, max=60),
      before_sleep=lambda retry_state: _capture_failed_usage_before_retry(retry_state, _global_failed_messages),
      retry_error_callback=lambda retry_state: _capture_failed_usage_before_retry(retry_state, _global_failed_messages)
    )
    async def run_stream_async(self, prompt: str) -> tuple[str, Usage]:
        """Run the agent with streaming and return complete response with usage."""
        global _global_failed_messages
        
        adapter = get_ui_adapter()
        
        # For text output, we use regular run method to avoid streaming issues
        # We can get rid of this by switching away from text output to structured output for the updated code
        if self._output_type is None:
            # Reset usage limits on retry attempts (they are fresh for each agent.run())
            limits = DEFAULT_USAGE_LIMITS.copy()
            usage_limits = UsageLimits(**limits)
            
            # Capture messages to calculate usage on failure
            with capture_run_messages() as messages:
                try:
                    result = await self.agent.run(prompt, usage_limits=usage_limits)
                except (UsageLimitExceeded, UnexpectedModelBehavior) as e:
                    # Store messages globally for the before_sleep callback
                    _global_failed_messages = list(messages)
                    logger.exception(f"Agent run_stream (text) failed: {type(e).__name__}")
                    adapter.show_error(f"{type(e).__name__}: {str(e)}")
                    raise
            
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
            
            # Capture messages to calculate usage on failure
            with capture_run_messages() as messages:
                try:
                    async with self.agent.run_stream(prompt, usage_limits=usage_limits) as result:
                        output = await result.get_output()
                        full_response = str(output)
                except (UsageLimitExceeded, UnexpectedModelBehavior) as e:
                    # Store messages globally for the before_sleep callback
                    _global_failed_messages = list(messages)
                    logger.exception(f"Agent run_stream (structured) failed: {type(e).__name__}")
                    adapter.show_error(f"{type(e).__name__}: {str(e)}")
                    raise
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
        
        try:
            return loop.run_until_complete(self.run_stream_async(prompt))
        except Exception as e:
            logger.exception(f"Agent run_stream (sync) failed: {type(e).__name__}")
            adapter = get_ui_adapter()
            adapter.show_error(f"{type(e).__name__}: {str(e)}")
            raise

def _capture_failed_usage_before_retry(retry_state, failed_messages=None):
    """Capture usage from failed request and add to iteration tracking before retry."""
    try:
        exception = retry_state.outcome.exception()
        print(f"Retrying prompt due to exception: {exception}")

        attempt = retry_state.attempt_number if retry_state else 1
        # Add separator to logs for retry attempts
        get_logger().write_kv("retry_attempt", str(attempt))
        get_logger().write_kv("exception", str(exception))

        if any(isinstance(exception, kind) for kind in (UsageLimitExceeded, UnexpectedModelBehavior)) \
         and failed_messages:
            # Calculate usage from the failed messages
            total_input_tokens = 0
            total_output_tokens = 0
            total_cache_tokens = 0
            
            for message in failed_messages:
                # Only responses have usage (request+response combined)
                # So if it fails on the request, there is no usage to capture
                # TODO we should go by pairs
                if hasattr(message, 'usage') and message.usage: 
                    total_input_tokens += getattr(message.usage, 'input_tokens', 0)
                    total_output_tokens += getattr(message.usage, 'output_tokens', 0)
                    total_cache_tokens += getattr(message.usage, 'cache_read_tokens', 0)
            
            if total_input_tokens > 0 or total_output_tokens > 0:
                failed_usage = Usage(
                    prompt_tokens=total_input_tokens,
                    completion_tokens=total_output_tokens,
                    cache_read_tokens=total_cache_tokens,
                )
                
                from vibenix.ui.conversation_templated import model_prompt_manager
                model_prompt_manager.add_iteration_usage(failed_usage)
            else:
                # Fallback: extract from exception message
                import re
                exc_str = str(exception)
                total_match = re.search(r'total_tokens=(\d+)', exc_str)
                if total_match:
                    total_tokens = int(total_match.group(1))
                    estimated_usage = Usage(
                        prompt_tokens=int(total_tokens * 0.8),
                        completion_tokens=int(total_tokens * 0.2),
                        cache_read_tokens=0,
                    )
                    
                    from vibenix.ui.conversation_templated import model_prompt_manager
                    model_prompt_manager.add_iteration_usage(estimated_usage)
                
    except Exception as e:
        logger.exception(f"Could not capture failed usage before retry: {type(e).__name__}")
        print(f"Could not capture failed usage before retry: {e}")
        # Don't let usage tracking errors break the retry flow
    finally:
        exception = retry_state.outcome.exception()
        if isinstance(exception, RetryError):
            raise exception
