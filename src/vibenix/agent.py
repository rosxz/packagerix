"""Pydantic-AI agent implementation for vibenix.

This module provides the core agent functionality using pydantic-ai.
"""

import asyncio
import json
from typing import Callable, Any, List, Optional
from pydantic_ai import Agent, UnexpectedModelBehavior, capture_run_messages, RunContext, PromptedOutput
from pydantic_ai.usage import UsageLimits
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError
from pydantic_ai.exceptions import UsageLimitExceeded, UnexpectedModelBehavior, ToolRetryError
from vibenix.model_config import get_model, use_prompted_output
from vibenix.ui.conversation import get_ui_adapter, Message, Actor, Usage
from vibenix.usage_utils import extract_usage_tokens
from vibenix.ccl_log import get_logger
from vibenix.model_config import DEFAULT_USAGE_LIMITS
import logging
import inspect
from functools import wraps
from pydantic_ai.messages import ModelMessage

logger = logging.getLogger(__name__)

# Global variable to store failed messages for retry callback
_global_failed_messages = None


class VibenixAgent:
    """Main agent for vibenix using pydantic-ai."""
    def __init__(self, output_type: type = None):
        """Initialize the agent with optional custom instructions and output type."""
        self.model = get_model()
        
        # Only pass output_type if it's not None
        if output_type is not None:
            # Use PromptedOutput mode for endpoints that don't reliably support tool-based structured outputs
            # (e.g., OpenRouter, AWS Bedrock). This is auto-detected in model_config.py
            if use_prompted_output():
                # Custom template with explicit instructions for clean JSON output
                # Note: curly braces must be doubled to escape them for str.format()
                json_template = (
                    "Respond with valid JSON matching this schema:\n"
                    "{schema}\n\n"
                    "IMPORTANT: Output ONLY the JSON object, with no additional text or markdown formatting.\n\n"
                    "Examples of correct JSON output:\n"
                    '- For enums: {{"response": "rust"}} or {{"response": "python"}}\n'
                    '- For lists: {{"response": ["item1", "item2"]}}\n'
                    '- For multi-line strings, use \\n for newlines (not \\\\n): '
                    '{{"code": "line1\\nline2\\nline3"}}'
                )
                self.agent = Agent(
                    model=self.model,
                    output_type=PromptedOutput(output_type, template=json_template),
                    retries=3,
                )
            else:
                self.agent = Agent(
                    model=self.model,
                    output_type=output_type,
                    retries=3,
                )
        else:
            self.agent = Agent(
                model=self.model,
                retries=3,
            )
        
        self._output_type = output_type  # Store output type for later checks
    
    def add_tool(self, func: Callable) -> None:
        # If RunContext needed, use agent.tool()
        # Otherwise, need to add or inject RunContext[<deps-type>] into each tool   
        self.agent.tool_plain(func, sequential=True)
    
    @retry(
      # model-behavior issues are handled by pydantic-ai's own internal retry mechanism on the Agent.
      retry=retry_if_exception_type(UsageLimitExceeded),
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=3, max=60),
      before_sleep=lambda retry_state: _capture_failed_usage_before_retry(retry_state, _global_failed_messages)
    )
    async def run_async(self, prompt: str, message_history: List[ModelMessage]=[]) -> tuple[Any, Usage]:
        """Run the agent asynchronously and return response with usage."""
        global _global_failed_messages
        
        # Reset usage limits on retry attempts (they are fresh for each agent.run())
        limits = DEFAULT_USAGE_LIMITS.copy()
        usage_limits = UsageLimits(**limits)
        
        # Capture messages to calculate usage on failure
        with capture_run_messages() as messages:
            try:
                result = await self.agent.run(prompt, usage_limits=usage_limits, message_history=message_history)
            except (UsageLimitExceeded, UnexpectedModelBehavior, ToolRetryError) as e:
                # Store messages globally for the before_sleep callback and log failure details
                _global_failed_messages = list(messages)
                _log_model_failure(messages, e)
                raise
        _log_internal_retry_responses(messages, level="warning", log_when_none=False)
        
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
    
    def run(self, prompt: str, message_history: List[ModelMessage]=[]) -> tuple[str, Usage]:
        """Run the agent synchronously."""
        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.run_async(prompt, message_history))
    
    @retry(
      # model-behavior issues are handled by pydantic-ai's own internal retry mechanism on the Agent.
      retry=retry_if_exception_type(UsageLimitExceeded),
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=3, max=60),
      before_sleep=lambda retry_state: _capture_failed_usage_before_retry(retry_state, _global_failed_messages),
      retry_error_callback=lambda retry_state: _capture_failed_usage_before_retry(retry_state, _global_failed_messages)
    )
    async def run_stream_async(self, prompt: str, message_history: List[ModelMessage]=[]) -> tuple[str, Usage]:
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
                    result = await self.agent.run(prompt, usage_limits=usage_limits, message_history=message_history)
                except (UsageLimitExceeded, UnexpectedModelBehavior, ToolRetryError) as e:
                    # Store messages globally for the before_sleep callback and log failure details
                    _global_failed_messages = list(messages)
                    _log_model_failure(messages, e)
                    raise
            _log_internal_retry_responses(messages, level="warning", log_when_none=False)
            
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
                    async with self.agent.run_stream(prompt, usage_limits=usage_limits, message_history=message_history) as result:
                        output = await result.get_output()
                        full_response = str(output)
                except (UsageLimitExceeded, UnexpectedModelBehavior, ToolRetryError) as e:
                    # Store messages globally for the before_sleep callback and log failure details
                    _global_failed_messages = list(messages)
                    _log_model_failure(messages, e)
                    raise
                _log_internal_retry_responses(messages, level="warning", log_when_none=False)
                print(full_response)
                
                # Get usage data
                usage_data = result.usage() if hasattr(result, 'usage') else None
                prompt_tokens, completion_tokens = extract_usage_tokens(usage_data)
                usage = Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cache_read_tokens=usage_data.cache_read_tokens if usage_data else 0,
                )
                
                return full_response, usage
    
    def run_stream(self, prompt: str, message_history: List[ModelMessage]=[]) -> tuple[str, Usage]:
        """Run the agent with streaming synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.run_stream_async(prompt, message_history))

def _capture_failed_usage_before_retry(retry_state, failed_messages=None):
    """Capture usage from failed request and add to iteration tracking before retry."""
    try:
        exception = retry_state.outcome.exception()
        print(f"Retrying prompt due to exception: {exception}")

        from vibenix.ui.conversation_templated import get_model_prompt_manager

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
        print(f"Could not capture failed usage before retry: {e}")
        # Don't let usage tracking errors break the retry flow
    finally:
        exception = retry_state.outcome.exception()
        if isinstance(exception, RetryError):
            raise exception

# DEBUGGING UTILS - Can remove at any point later
def _log_model_failure(messages, exception):
    """Log minimal details about model output before validation/tool errors.

    This helps diagnose UnexpectedModelBehavior / ToolRetryError cases by
    recording the last model-related message without dumping huge transcripts.
    """
    try:
        logger.error("Model failure: %s: %s", type(exception).__name__, str(exception))

        if not messages:
            return

        #logger.error("Captured model messages for this run (may include multiple retries):")

        #for idx, msg in enumerate(messages):
        #    content = _extract_message_content(msg)
        #    if content is not None:
        #        logger.error("  Message %d content: %s", idx, content[:2000])
        #    else:
        #        logger.error("  Message %d (repr): %r", idx, msg)

        #_log_internal_retry_responses(messages, level="error", log_when_none=True)
    except Exception as log_exc:
        # Never let logging failures interfere with the main error path
        logger.warning("Failed to log model failure details: %s", log_exc)


def _extract_message_content(message) -> Optional[str]:
    """Best-effort extraction of readable content from pydantic-ai messages."""
    try:
        # Some message objects may expose direct content-like fields
        for attr in ("content", "text", "output", "message"):
            if hasattr(message, attr):
                value = getattr(message, attr)
                if value:
                    return str(value)

        parts = getattr(message, "parts", None)
        if not parts:
            return None

        chunks = []
        for part in parts:
            part_type = type(part).__name__
            part_content = None

            if hasattr(part, "content") and getattr(part, "content"):
                part_content = str(getattr(part, "content"))
            elif hasattr(part, "text") and getattr(part, "text"):
                part_content = str(getattr(part, "text"))
            elif hasattr(part, "args") and getattr(part, "args") is not None:
                part_content = str(getattr(part, "args"))
            elif hasattr(part, "tool_name") and getattr(part, "tool_name"):
                part_content = f"tool={getattr(part, 'tool_name')}"
            else:
                part_content = str(part)

            chunks.append(f"[{part_type}] {part_content}")

        return "\n".join(chunks)
    except Exception:
        return None


def _serialize_message_raw(message) -> str:
    """Serialize message in a raw form (prefer JSON) for debugging schema mismatches."""
    try:
        if hasattr(message, "model_dump_json"):
            return message.model_dump_json()

        if hasattr(message, "model_dump"):
            return json.dumps(message.model_dump(), default=str)

        if hasattr(message, "__dict__"):
            return json.dumps(message.__dict__, default=str)

        return str(message)
    except Exception:
        return repr(message)


def _has_retry_prompt_part(message) -> bool:
    """Check whether a message includes a pydantic-ai RetryPromptPart."""
    try:
        parts = getattr(message, "parts", None)
        if not parts:
            return False
        return any(type(part).__name__ == "RetryPromptPart" for part in parts)
    except Exception:
        return False


def _is_model_response_message(message) -> bool:
    """Check whether message looks like a model response message."""
    try:
        if type(message).__name__ == "ModelResponse":
            return True

        parts = getattr(message, "parts", None)
        if not parts:
            return False

        response_like_part_names = {
            "TextPart",
            "ThinkingPart",
            "ToolCallPart",
            "BuiltinToolCallPart",
            "BuiltinToolReturnPart",
            "ToolReturnPart",
        }
        return any(type(part).__name__ in response_like_part_names for part in parts)
    except Exception:
        return False


def _log_internal_retry_responses(messages, level: str = "warning", log_when_none: bool = False) -> None:
    """Log model response content that led to each internal pydantic-ai retry."""
    try:
        log_func = getattr(logger, level, logger.warning)
        retry_count = 0

        for idx, message in enumerate(messages):
            if not _has_retry_prompt_part(message):
                continue

            retry_count += 1
            retry_prompt_content = _extract_message_content(message)

            prev_response_content = None
            prev_response_index = None
            for prev_idx in range(idx - 1, -1, -1):
                candidate = messages[prev_idx]
                if _is_model_response_message(candidate):
                    prev_response_index = prev_idx
                    prev_response_content = _extract_message_content(candidate)
                    break

            log_func("Internal pydantic-ai retry #%d detected.", retry_count)

            current_retry_message_content = _extract_message_content(message)
            log_func(
                "  Current retry-triggering message (message %d): %s",
                idx,
                (current_retry_message_content or "<no extractable content>")[:2000],
            )

            if prev_response_index is not None:
                log_func(
                    "  Response that led to retry (message %d): %s",
                    prev_response_index,
                    (prev_response_content or "<no extractable content>")[:2000],
                )
            else:
                log_func("  Could not find preceding model response for this retry.")

            if retry_prompt_content:
                log_func("  Retry prompt details: %s", retry_prompt_content[:2000])

        if retry_count == 0 and log_when_none:
            log_func("No internal pydantic-ai retry prompts were captured in messages.")
    except Exception as e:
        logger.warning("Could not log internal retry response details: %s", e)
#### END OF DEBUGGING UTILS

def tool_wrapper(original_func):
    """Decorator to wrap tool functions for usage tracking."""
    @wraps(original_func)
    def wrapper(*args, **kwargs):
        """Wrapper to track tool usage (currently limited in accuracy)."""
        from vibenix.ui.conversation_templated import get_model_prompt_manager

        # Call the original function and get the result
        result = original_func(*args, **kwargs)

        # Estimate tokens from result
        import tiktoken
        encoder = tiktoken.encoding_for_model("gpt-4-1106-preview")
        tool_in = len(encoder.encode(str(result)))
        # Estimate tokens str forming: "function_name(arg1, arg2, karg1=value1, ...)"
        tool_call_str = f"{original_func.__name__}(" + ", ".join(
            [str(a) for a in args] +
            [f"{k}={v}" for k, v in kwargs.items()]
        ) + ")"
        tool_out = len(encoder.encode(tool_call_str)) # Call is done as output tokens (reasoning)
        
        get_model_prompt_manager().add_session_tool_usage(original_func.__name__, prompt=tool_in, completion=tool_out)
        return result

    return wrapper
