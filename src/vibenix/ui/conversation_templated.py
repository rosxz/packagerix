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
    Usage,
    Message,
    Actor,
    get_ui_adapter
)

from vibenix.packaging_flow.model_prompts.prompt_loader import get_prompt_loader
from vibenix.agent import VibenixAgent
from abc import ABC

T = TypeVar('T')

class ModelPromptManager:
    """Manages model prompt interactions and tracks usage across a session."""
    ### Cost tracking
    def __init__(self, model: str):
        self._session_usage = Usage(model=model)
        self._iteration_usage = Usage(model=model)
        self._model = model
    
    def get_session_cost(self):
        """Get the accumulated cost for this session."""
        self.reset_iteration_usage()
        return self._session_usage.calculate_cost()

    def get_session_usage(self) -> Usage:
        """Get the accumulated usage for this session."""
        self.reset_iteration_usage()
        return self._session_usage

    def get_iteration_usage(self) -> Usage:
        """Get usage for the last model interactions."""
        usage = self._iteration_usage
        self.reset_iteration_usage()
        return usage

    def reset_iteration_usage(self):
        """Reset the iteration usage counters."""
        self._session_usage.prompt_tokens += self._iteration_usage.prompt_tokens
        self._session_usage.completion_tokens += self._iteration_usage.completion_tokens
        self._iteration_usage = Usage(model=self._model)
    #####

    def ask_model_prompt(self, template_path: str, functions: Optional[List[Callable]] = None):
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
            # OutputFunctions returntype workaround -> check if the class is abstract
            if inspect.isclass(return_type) and (ABC in return_type.__bases__):
                # Get the same named method from the return type class
                return_type = getattr(return_type, return_type.__name__, None)

            # Determine output type and whether to use streaming
            is_streaming = return_type == str
            is_enum = inspect.isclass(return_type) and issubclass(return_type, Enum)
            is_structured = return_type not in [str, type(None)]
            
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
                first_line = f"({template_path}): " + rendered_prompt.split('\n')[0]
                coordinator_msg = f"@model {first_line}" if len(rendered_prompt) > 100 else f"@model {rendered_prompt}"
                adapter.show_message(Message(Actor.COORDINATOR, coordinator_msg))
                
                # Create agent with appropriate output type
                if is_structured:
                    # For structured outputs (enums, lists, etc.), use output_type
                    agent = VibenixAgent(output_type=return_type)
                else:
                    # For strings, we don't need structured output
                    agent = VibenixAgent()
                
                # Add tools to the agent
                all_functions = (functions or []) + additional_functions
                from vibenix.packaging_flow.model_prompts import EDIT_FUNCTIONS
                for tool_func in all_functions:
                    agent.add_tool(tool_func)
                
                # Run the agent
                if is_streaming:
                    # For string returns, use streaming
                    response, usage = agent.run_stream(rendered_prompt)
                    result = response
                    get_logger().reply_chunk_text(0, result, 4)
                else:
                    # For non-streaming (structured outputs), just run normally
                    response, usage = agent.run(rendered_prompt)
                    
                    # Pydantic-ai should return the structured type directly
                    result = response
                    adapter.show_message(Message(Actor.MODEL, str(result)))
                    if is_structured:
                        if is_enum:
                            get_logger().reply_chunk_typed(0, result, 'enum', 4)
                        else:
                            get_logger().reply_chunk_typed(0, result, str(type(result)), 4)
                    else:
                        get_logger().reply_chunk_text(0, result, 4)
                
                get_logger().prompt_end(2)
                
                # Track usage for cost calculations
                self._iteration_usage.prompt_tokens += usage.prompt_tokens
                self._iteration_usage.completion_tokens += usage.completion_tokens
                return result
            
            return wrapper
        return decorator

from vibenix.model_config import get_model_name
model_prompt_manager = ModelPromptManager(get_model_name())
