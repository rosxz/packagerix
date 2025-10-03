"""Unified template-based decorator for model conversations using Chat API."""

from functools import wraps
from typing import Callable, TypeVar, Optional, List, Any, get_type_hints, Tuple, get_origin, get_args
import os
from pathlib import Path
from enum import Enum
import inspect
from pydantic import BaseModel

from magentic import Chat, UserMessage, StreamedResponse, StreamedStr, FunctionCall, ToolResultMessage
from magentic.chat_model.message import Usage
from vibenix.ccl_log import get_logger
from vibenix.ui.conversation import (
    Message, Actor, get_ui_adapter, _retry_with_rate_limit, 
    handle_model_chat
)
from vibenix.packaging_flow.model_prompts.prompt_loader import get_prompt_loader


T = TypeVar('T')


def ask_model_prompt(template_path: str, functions: Optional[List[Callable]] = None):
    """Unified decorator for model interactions using prompt templates.
    
    This decorator:
    - Loads prompts from template files
    - Supports streaming (StreamedStr) and structured returns (Enum, Pydantic models, basic types)
    - Integrates with magentic's Chat API for function calling
    - Handles all return type conversions automatically
    - Returns a tuple of (result, usage) where usage contains token counts
    
    Args:
        template_path: Path to template file relative to model_prompts directory
        functions: Optional list of functions to make available to the model
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Get return type hint
        type_hints = get_type_hints(func)
        return_type = type_hints.get('return', type(None))
        
        is_streaming = return_type == StreamedStr
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            adapter = get_ui_adapter()
            
            # Get function signature to map args to param names
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Filter out None values and empty lists from arguments
            template_context = {
                k: v for k, v in bound_args.arguments.items() 
                if v is not None and v != []
            }
            
            # Special handling for additional_functions parameter
            additional_functions = template_context.pop('additional_functions', [])

            get_logger().prompt_begin(func.__name__, template_path, 2, template_context)
            
            # Load and render the template
            prompt_loader = get_prompt_loader()
            rendered_prompt = prompt_loader.load(template_path, **template_context)
            
            # Show coordinator message (first line or whole prompt if short)
            first_line = f"({template_path}): " + rendered_prompt.split('\n')[0]
            coordinator_msg = f"@model {first_line}" if len(rendered_prompt) > 100 else f"@model {rendered_prompt}"
            adapter.show_message(Message(Actor.COORDINATOR, coordinator_msg))
            
            # Create chat with the rendered prompt
            chat_functions = (functions or []) + additional_functions
            
            if is_streaming:
                # For streaming responses, use StreamedResponse output type
                chat = Chat(
                    messages=[UserMessage(rendered_prompt)],
                    functions=chat_functions,
                    output_types=[StreamedResponse],
                )
            else:
                # For structured types (enums, pydantic models, basic types), use the actual return type
                chat = Chat(
                    messages=[UserMessage(rendered_prompt)],
                    functions=chat_functions,
                    output_types=[return_type, FunctionCall] if return_type != type(None) else None,
                )
            
            def _execute_chat():
                if is_streaming:
                    # For streaming, submit the chat and use handle_model_chat
                    submitted_chat = _retry_with_rate_limit(chat.submit)
                    # Check if tool_call_collector was passed in kwargs
                    tool_call_collector = template_context.get('tool_call_collector')
                    result, usage = handle_model_chat(submitted_chat, tool_call_collector)
                    
                    get_logger().prompt_end(2)
              
                    return result
                else:
                    # For structured types (enums, pydantic models, basic types)
                    def _handle_function_call(item, response_chunk_num, current_chat):
                        """Execute a function call and return updated chat."""
                        tool_call_collector = template_context.get('tool_call_collector')
                        if tool_call_collector is not None:
                            tool_call_collector.append({
                                'function': item.function.__name__,
                                'arguments': item.arguments
                            })

                        get_logger().reply_chunk_function_call(response_chunk_num, 4)
                        function_result = item()
                        adapter.show_message(Message(Actor.MODEL, str(function_result)))
                        return current_chat.add_message(ToolResultMessage(function_result, item._unique_id))

                    def _get_structured_result():
                        current_chat = _retry_with_rate_limit(chat.submit)
                        response_chunk_num = 0

                        while True:
                            content = current_chat.last_message.content

                            # Handle single FunctionCall
                            if isinstance(content, FunctionCall):
                                current_chat = _handle_function_call(content, response_chunk_num, current_chat)
                                current_chat = _retry_with_rate_limit(current_chat.submit)
                                response_chunk_num += 1
                                continue

                            # Content should be the final structured result
                            typed = str(content.__class__.__name__) if content is not None else None
                            display_text = f"[{typed}] {str(content)}"

                            adapter.show_message(Message(Actor.MODEL, display_text))
                            get_logger().reply_chunk_typed(response_chunk_num, content, typed, 4)
                            get_logger().prompt_end(2)
                            return content

                    # Use retry wrapper for the entire structured result function
                    return _retry_with_rate_limit(_get_structured_result)
            
            try:
                return _execute_chat()
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                error_msg = f"Error in model function {func.__name__}: {str(e)}\n{tb}"
                from vibenix.ui.logging_config import logger
                logger.error(error_msg)
                raise
        
        return wrapper
    return decorator
