"""Template-based model conversation helpers for vibenix.

This module provides utilities for loading prompt templates and asking models questions.
"""

import os
import inspect
from pathlib import Path
from enum import Enum
from typing import TypeVar, Union, get_origin, get_args, Any, Optional, List, Callable, get_type_hints
from functools import wraps
from vibenix.ccl_log import get_logger
from vibenix.ui.conversation import (
    handle_model_chat,
    Usage,
    Message,
    Actor,
    get_ui_adapter
)
from vibenix.packaging_flow.model_prompts.prompt_loader import get_prompt_loader
from vibenix.agent import VibenixAgent

T = TypeVar('T')


def ask_model_prompt(template_path: str, functions: Optional[List[Callable]] = None):
    """Decorator for model interactions using prompt templates.
    
    This decorator uses pydantic-ai to interact with the model.
    
    Args:
        template_path: Path to template file relative to model_prompts directory
        functions: Optional list of functions to make available to the model
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Get return type hint
        type_hints = get_type_hints(func)
        return_type = type_hints.get('return', type(None))
        
        # Determine if this returns str or an Enum
        is_streaming = return_type == str
        is_enum = inspect.isclass(return_type) and issubclass(return_type, Enum)
        
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
            tool_call_collector = template_context.pop('tool_call_collector', None)
            
            get_logger().prompt_begin(func.__name__, template_path, 2, template_context)
            
            # Load and render the template
            prompt_loader = get_prompt_loader()
            rendered_prompt = prompt_loader.load(template_path, **template_context)
            
            # Show coordinator message (first line or whole prompt if short)
            first_line = rendered_prompt.split('\n')[0]
            coordinator_msg = f"@model {first_line}" if len(rendered_prompt) > 100 else f"@model {rendered_prompt}"
            adapter.show_message(Message(Actor.COORDINATOR, coordinator_msg))
            
            # Create agent with appropriate output type
            if is_enum:
                # For enums, pydantic-ai can handle them directly as output_type
                agent = VibenixAgent(output_type=return_type)
            else:
                # For strings, we don't need structured output
                agent = VibenixAgent()
            
            # Add tools to the agent
            all_functions = (functions or []) + additional_functions
            for tool_func in all_functions:
                agent.add_tool(tool_func)
            
            # Run the agent
            if is_streaming:
                # For string returns, use streaming
                response, usage = agent.run_stream(rendered_prompt)
                result = response
                get_logger().reply_chunk_text(0, result, 4)
            else:
                # For non-streaming (like enums), just run normally
                response, usage = agent.run(rendered_prompt)
                
                if is_enum:
                    # Pydantic-ai should return the enum directly
                    result = response
                    adapter.show_message(Message(Actor.MODEL, str(result)))
                    get_logger().reply_chunk_enum(0, result, 4)
                else:
                    result = response
                    adapter.show_message(Message(Actor.MODEL, str(result)))
                    get_logger().reply_chunk_text(0, result, 4)
            
            get_logger().prompt_end(2)
            
            # TODO: Track usage for cost calculations
            # For now, usage is tracked internally but not returned
            
            return result
        
        return wrapper
    return decorator