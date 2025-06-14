"""Coordinator pattern for packagerix - separates business logic from UI."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, TypeVar
from functools import wraps
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import asyncio
from concurrent.futures import Future
import threading
from magentic import StreamedStr

# Type variable for function return types
T = TypeVar('T')


class Actor(Enum):
    """The three actors in the packagerix conversation."""
    COORDINATOR = "coordinator"
    MODEL = "model"
    USER = "user"


@dataclass
class Message:
    """A message in the conversation."""
    actor: Actor
    content: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class UIAdapter(ABC):
    """Abstract base class for UI adapters - all methods are synchronous from coordinator's perspective."""
    
    @abstractmethod
    def ask_user(self, prompt: str) -> str:
        """Ask the user for input and return the complete response."""
        pass
    
    @abstractmethod
    def handle_model_streaming(self, streamed_result) -> str:
        """Handle streaming from a model response. Returns the complete response as a string."""
        pass
    
    @abstractmethod
    def show_message(self, message: Message):
        """Display a message from any actor."""
        pass
    
    @abstractmethod
    def show_error(self, error: str):
        """Display an error message."""
        pass
    
    @abstractmethod
    def show_progress(self, message: str):
        """Show a progress update."""
        pass


class TerminalUIAdapter(UIAdapter):
    """Terminal-based UI adapter for CLI mode."""
    
    def __init__(self):
        pass
    
    def ask_user(self, prompt: str) -> str:
        """Ask user for input via terminal."""
        self.show_message(Message(Actor.COORDINATOR, prompt))
        
        # Simple synchronous input
        response = input("")
        
        self.show_message(Message(Actor.USER, response))
        return response
    
    def handle_model_streaming(self, streamed_result) -> str:
        """Handle streaming from a model response."""
        from packagerix.ui.logging_config import logger
        from magentic import StreamedStr
        
        if not isinstance(streamed_result, StreamedStr):
            raise TypeError(f"Expected StreamedStr, got {type(streamed_result)}")
        
        logger.info("🤖 model: ", end="")
        
        full_response = ""
        for chunk in streamed_result:
            full_response += chunk
            print(chunk, end="", flush=True)
        
        print()  # newline at end
        return full_response
    
    def show_message(self, message: Message):
        """Display a message in terminal."""
        from packagerix.ui.logging_config import logger
        
        actor_symbol = {
            Actor.COORDINATOR: "🎯",
            Actor.MODEL: "🤖",
            Actor.USER: "👤"
        }
        
        formatted = f"\n{actor_symbol[message.actor]} {message.actor.value}: {message.content}"
        logger.info(formatted)
    
    def show_error(self, error: str):
        """Display error in terminal."""
        from packagerix.ui.logging_config import logger
        logger.error(f"❌ Error: {error}")
    
    def show_progress(self, message: str):
        """Show progress in terminal."""
        from packagerix.ui.logging_config import logger
        logger.info(f"⏳ {message}")


# Global UI adapter instance
_ui_adapter: Optional[UIAdapter] = None


def set_ui_adapter(adapter: UIAdapter):
    """Set the global UI adapter."""
    global _ui_adapter
    _ui_adapter = adapter


def get_ui_adapter() -> UIAdapter:
    """Get the current UI adapter, defaulting to terminal."""
    global _ui_adapter
    if _ui_adapter is None:
        _ui_adapter = TerminalUIAdapter()
    return _ui_adapter


def ask_user(prompt_text: str):
    """Decorator for functions that need user input. Prompt should start with '@user'."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            adapter = get_ui_adapter()
            
            # Simple synchronous call - adapter handles any async internally
            user_input = adapter.ask_user(prompt_text)
            
            # Call the original function with user input as first argument
            return func(user_input, *args, **kwargs)
        
        return wrapper
    return decorator


def ask_model(prompt_text: str):
    """Decorator for functions that need model input. Should only be used on stub functions.
    
    This decorator:
    1. Applies the @prompt decorator with the given prompt
    2. Shows the coordinator message in the UI
    3. Handles streaming responses
    4. Returns the complete string
    """
    def decorator(func: Callable[..., StreamedStr]) -> Callable[..., str]:
        # Apply the prompt decorator using the same prompt text
        from magentic import prompt, StreamedStr
        prompt_decorated_func = prompt(prompt_text.replace("@model ", ""))(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> str:
            adapter = get_ui_adapter()
            max_retries = 30
            base_delay = 5  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Show the coordinator message (only on first attempt)
                    if attempt == 0:
                        adapter.show_message(Message(Actor.COORDINATOR, prompt_text))
                    else:
                        from packagerix.ui.logging_config import logger
                        logger.info(f"Retrying model call (attempt {attempt + 1}/{max_retries})")
                    
                    # Call the prompt-decorated function to get StreamedStr
                    streamed_result = prompt_decorated_func(*args, **kwargs)
                    
                    if streamed_result is None:
                        raise ValueError(f"Model function {func.__name__} returned None - this indicates a problem with the prompt or model configuration")
                    
                    # Handle the streaming in the adapter and return final string
                    return adapter.handle_model_streaming(streamed_result)
                    
                except Exception as e:
                    # Import litellm to check for InternalServerError
                    try:
                        import litellm
                        is_overload_error = isinstance(e, litellm.InternalServerError)
                    except ImportError:
                        is_overload_error = False
                    
                    if is_overload_error and attempt < max_retries - 1:
                        # Wait with exponential backoff, capped at 10 minutes
                        delay = min(base_delay * (1.16 ** attempt), 600)
                        from packagerix.ui.logging_config import logger
                        logger.warning(f"API overloaded, waiting {delay} seconds before retry...")
                        import time
                        time.sleep(delay)
                        continue
                    else:
                        # Either not an overload error, or we've exhausted retries
                        import traceback
                        tb = traceback.format_exc()
                        error_msg = f"Error in model function {func.__name__}: {str(e)}\n{tb}"
                        from packagerix.ui.logging_config import logger
                        logger.error(error_msg)
                        raise
        
        return wrapper
    return decorator


def ask_model_enum(prompt_text: str):
    """Decorator for functions that need model input and return an Enum. Should only be used on stub functions.
    
    This decorator:
    1. Applies the @prompt decorator with the given prompt
    2. Shows the coordinator message in the UI  
    3. Handles non-streaming responses
    4. Converts string result to Enum based on function's return type annotation
    """
    def decorator(func: Callable) -> Callable:
        # Apply the prompt decorator using the same prompt text
        from magentic import prompt
        import inspect
        from enum import Enum
        
        # Get the return type annotation
        sig = inspect.signature(func)
        return_type = sig.return_annotation
        
        # Check if return type is an Enum
        if not (inspect.isclass(return_type) and issubclass(return_type, Enum)):
            raise TypeError(f"ask_model_enum can only be used with functions that return Enum types, got {return_type}")
        
        prompt_decorated_func = prompt(prompt_text.replace("@model ", ""))(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            adapter = get_ui_adapter()
            max_retries = 30
            base_delay = 5  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Show the coordinator message (only on first attempt)
                    if attempt == 0:
                        adapter.show_message(Message(Actor.COORDINATOR, prompt_text))
                    else:
                        from packagerix.ui.logging_config import logger
                        logger.info(f"Retrying model call (attempt {attempt + 1}/{max_retries})")
                    
                    # Call the prompt-decorated function to get result
                    result = prompt_decorated_func(*args, **kwargs)
                    
                    if result is None:
                        raise ValueError(f"Model function {func.__name__} returned None - this indicates a problem with the prompt or model configuration")
                    
                    # Convert result to Enum if needed
                    if isinstance(result, return_type):
                        # Already the correct enum type
                        return result
                    elif isinstance(result, str):
                        # String result, convert to enum
                        try:
                            return return_type(result.strip())
                        except ValueError:
                            # If direct conversion fails, try by name
                            return return_type[result.strip()]
                    else:
                        # Try to convert whatever we got
                        return return_type(str(result).strip())
                        
                except Exception as e:
                    # Import litellm to check for InternalServerError
                    try:
                        import litellm
                        is_overload_error = isinstance(e, litellm.InternalServerError)
                    except ImportError:
                        is_overload_error = False
                    
                    if is_overload_error and attempt < max_retries - 1:
                        # Wait with exponential backoff, capped at 10 minutes
                        delay = min(base_delay * (1.16 ** attempt), 600)
                        from packagerix.ui.logging_config import logger
                        logger.warning(f"API overloaded, waiting {delay} seconds before retry...")
                        import time
                        time.sleep(delay)
                        continue
                    else:
                        # Either not an overload error, or we've exhausted retries
                        import traceback
                        tb = traceback.format_exc()
                        error_msg = f"Error in model function {func.__name__}: {str(e)}\n{tb}"
                        from packagerix.ui.logging_config import logger
                        logger.error(error_msg)
                        raise
        
        return wrapper
    return decorator


def coordinator_message(content: str):
    """Send a message from the coordinator."""
    adapter = get_ui_adapter()
    adapter.show_message(Message(Actor.COORDINATOR, content))


def coordinator_error(error: str):
    """Show an error from the coordinator."""
    adapter = get_ui_adapter()
    adapter.show_error(error)


def coordinator_progress(message: str):
    """Show a progress update from the coordinator."""
    adapter = get_ui_adapter()
    adapter.show_progress(message)