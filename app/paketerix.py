#!/usr/bin/env python3
"""Paketerix - AI-powered Nix package builder.

Main entry point that supports both terminal and textual UI modes.
"""

import argparse
import os
import sys
from pydantic import BaseModel
from magentic import prompt, prompt_chain, StreamedStr
from magentic import (
    chatprompt,
    AssistantMessage,
    FunctionCall,
    FunctionResultMessage,
    UserMessage,
    SystemMessage
)

from app.logging_config import logger  # Import logger first to ensure it's initialized
from app import config
import litellm
from typing import Optional
from functools import wraps
import hashlib
import json

config.init()

from app.nix import Error, get_last_ten_lines, test_updated_code
from app.flake import init_flake
from app.parsing import scrape_and_process, extract_updated_code, cache

# Check which backend we're using
magentic_backend = os.environ.get("MAGENTIC_BACKEND", "litellm")
logger.info(f"Using magentic backend: {magentic_backend}")

# Global variable to track if we're in UI mode
_ui_mode = False

def set_ui_mode(ui_mode: bool):
    """Set whether we're running in UI mode."""
    global _ui_mode
    _ui_mode = ui_mode

import logging
if "OLLAMA_HOST" in os.environ:
    logger.info(f"OLLAMA_HOST is set to: {os.environ['OLLAMA_HOST']}")
else:
    logger.warning("OLLAMA_HOST environment variable is not set")

#litellm.set_verbose=True
# litellm.set_verbose=True

# Note: Do NOT set litellm.api_base globally as it affects all models
# Instead, Ollama models should specify api_base per request
# or use LITELLM_LOG=DEBUG to see endpoint selection
if "OLLAMA_HOST" in os.environ:
    logger.info(f"OLLAMA_HOST available at: {os.environ['OLLAMA_HOST']}")
    logger.info("Note: api_base will be set per-model, not globally")

# Function calling is not supported by anthropic. To add it to the prompt, set
litellm.add_function_to_prompt = True

def cache_streaming_response(func):
    """Decorator that caches streaming responses.
    
    For cached results, yields the cached string as a single chunk.
    For new results, streams the response and caches the complete result.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Create a cache key from function name and arguments
        # Convert args to a hashable format
        key_data = {
            'func_name': func.__name__,
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        cache_key = hashlib.md5(key_str.encode()).hexdigest()
        
        # Check if we have a cached result
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Using cached result for {func.__name__}")
            # Return a generator that yields the cached result
            def cached_generator():
                yield cached_result
            return cached_generator()
        
        # No cached result, call the original function
        logger.info(f"No cached result, calling {func.__name__}")
        stream = func(*args, **kwargs)
        
        # Collect the stream and yield chunks
        chunks = []
        def caching_generator():
            for chunk in stream:
                chunks.append(chunk)
                yield chunk
            
            # After streaming is complete, cache the full result
            full_result = ''.join(chunks)
            cache.set(cache_key, full_result)
            logger.info(f"Cached result for {func.__name__}")
        
        return caching_generator()
    
    return wrapper

class Project(BaseModel):
    name: str
    latest_commit_sha1: str
    version_tag : Optional[str]
    dependencies: list[str]

from app.coordinator import ask_model

@ask_model("""@model You are software packaging expert who can build any project using the Nix programming language.

Read the contents of the project's GitHub page and fill out all of the sections in the code template that are marked with ... .
Do not make any other modifications. Do not modify lib.fakeHash.

Your goal is to make the build progress further, but without adding any unnecessary configuration or dependencies.

This is the code template you have to fill out:

```nix
{code_template}
```   

Here is the information form the project's GitHub page:

```text
{project_page}
```

Note: your reply should contain exaclty one code block with the updated Nix code.
""")
def set_up_project (code_template: str, project_page: str) -> StreamedStr : ...

@prompt("""
You are software packaging expert who can build any project using the Nix programming language.

Read the contents of the project's GitHub page and return the following information.
    1. The build tool which should be invoked to build the project.
    2. A list of build tools and project dependencies.
    3. A list of other information which might be necessary for buiding the project.
""")
def identify_dependencies (code_template: str, project_page: str) -> str : ...

@ask_model("""@model You are software packaging expert who can build any project using the Nix programming language.

Read the contents of the project's GitHub page and summarize it.
Include information like
    1. The build tool which should be invoked to build the project.
    2. A list of build tools and project dependencies.
    3. Other information which might be necessary for buiding the project.
    
    Do not include information which is irrelevant for building the project.
Here is the information form the project's GitHub page:

```text
{project_page}
```
""")
def summarize_github (project_page: str) -> StreamedStr : ...

#def eval_plan_to_make_progress_valid


def mock_input (ask : str, reply: str):
    logger.info(ask)
    logger.info(reply + "\n")
    return reply

def run_terminal_ui():
    """Run the terminal-based interface."""
    from app.logging_config import enable_console_logging
    enable_console_logging()
    
    set_ui_mode(False)
    
    # Use the coordinator pattern for CLI
    from app.coordinator import set_ui_adapter, TerminalUIAdapter
    from app.packaging_coordinator import run_packaging_flow
    from app.terminal_model_config import ensure_model_configured
    
    # Set up terminal UI adapter
    set_ui_adapter(TerminalUIAdapter())
    
    # Ensure model is configured before running
    if not ensure_model_configured():
        logger.error("Model configuration required to continue")
        sys.exit(1)
    
    # Run the packaging flow in background thread (like textual UI)
    import threading
    
    def run_coordinator():
        try:
            run_packaging_flow()
        except Exception as e:
            logger.error(f"Error in packaging flow: {e}")
            import traceback
            traceback.print_exc()
    
    coordinator_thread = threading.Thread(target=run_coordinator)
    coordinator_thread.daemon = True
    coordinator_thread.start()
    
    # Wait for completion
    coordinator_thread.join()


def run_textual_ui():
    """Run the textual-based interface."""
    from app.textual_ui import PaketerixChatApp
    app = PaketerixChatApp()
    app.run()


# The ensure_model_configured function is now handled by UI-specific implementations


def main():
    """Main entry point for paketerix."""
    parser = argparse.ArgumentParser(
        description="Paketerix - AI-powered Nix package builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  paketerix                    # Run with interactive textual UI
  paketerix --raw             # Run with terminal-only interface
  paketerix --help            # Show this help
"""
    )
    
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Use terminal-only interface instead of textual UI"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="paketerix 0.1.0"
    )
    
    args = parser.parse_args()
    
    try:
        if args.raw:
            logger.info("Starting paketerix in terminal mode")
            run_terminal_ui()
        else:
            logger.info("Starting paketerix in textual UI mode")
            run_textual_ui()
    except KeyboardInterrupt:
        logger.info("\nExiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
