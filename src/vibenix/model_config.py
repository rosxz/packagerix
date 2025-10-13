"""Model configuration for pydantic-ai integration.

This module provides model configuration compatible with the previous litellm-based system.
"""

import os
import json
from typing import Optional, Dict, Any, Tuple
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.openai import OpenAIModelSettings
from vibenix.ui.logging_config import logger


# Default model settings for different providers
DEFAULT_MODEL_SETTINGS = {
    "gemini": {
        "max_tokens": 32768,     # 32k tokens for complex packaging scenarios
        "temperature": 0.1,      # Lower temperature for focused responses
        "thinking_budget": 8192  # 8k tokens for reasoning about tool calls
    },
    "openai": {
        "max_tokens": 32768,     # Match Gemini for consistency
        "temperature": 0.1       # Lower temperature for focused responses
    }
}

# Cache for model configuration to avoid repeated loading and logging
_cached_config = None
_cached_model = None


def load_saved_configuration() -> Optional[Tuple[str, str, Optional[str], Optional[str], Optional[Dict]]]:
    """Load previously saved configuration, returns (provider_name, model, ollama_host, openai_api_base, model_settings).
    
    This maintains compatibility with the previous configuration format.
    """
    try:
        config_path = os.path.expanduser("~/.vibenix/config.json")
        
        if os.path.exists(config_path):
            with open(config_path) as f:
                config_data = json.load(f)
            
            # Extract configuration
            provider_name = config_data.get("provider")
            model = config_data.get("model")
            ollama_host = config_data.get("ollama_host")
            openai_api_base = config_data.get("openai_api_base")
            model_settings = config_data.get("model_settings", {})
            
            if provider_name and model:
                # Set OPENAI_BASE_URL if using OpenAI with custom endpoint
                if provider_name == "openai" and openai_api_base:
                    os.environ["OPENAI_BASE_URL"] = openai_api_base
                
                return provider_name, model, ollama_host, openai_api_base, model_settings
            
    except Exception as e:
        logger.warning(f"Could not load saved configuration: {e}")
    
    return None


def get_model_config() -> dict:
    """Get the model configuration from saved config or defaults."""
    global _cached_config
    
    # Return cached config if available
    if _cached_config is not None:
        return _cached_config
    
    # Try to load saved configuration
    saved_config = load_saved_configuration()
    
    if saved_config:
        provider_name, model, ollama_host, openai_api_base, model_settings = saved_config
        
        # Remove provider prefix from model if present
        if "/" in model:
            model_name = model.split("/", 1)[1]
        else:
            model_name = model
        
        # Determine base URL
        if openai_api_base:
            base_url = openai_api_base
        elif ollama_host:
            base_url = ollama_host
        else:
            base_url = "http://llama.digidow.ins.jku.at:11434/v1/"
        
        # Ensure base URL ends with /v1/ for OpenAI compatibility
        if not base_url.endswith("/v1/") and not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1/"
        
        _cached_config = {
            "provider": provider_name,
            "model_name": model_name,
            "base_url": base_url,
            "full_model": model,
            "model_settings": model_settings or {}
        }
    else:
        # Default configuration
        logger.info("No saved configuration found, using defaults")
        _cached_config = {
            "provider": "openai",
            "model_name": "qwen3-coder-30b-a3b",
            "base_url": "http://llama.digidow.ins.jku.at:11434/v1/",
            "full_model": "openai/qwen3-coder-30b-a3b",
            "model_settings": {}
        }
    
    return _cached_config


def get_model():
    """Get the model instance, creating it if necessary."""
    global _cached_model
    
    if _cached_model is None:
        # This should only happen if initialize_model_config wasn't called
        raise RuntimeError("Model not initialized. Call initialize_model_config() first.")
    
    return _cached_model



def get_model_name() -> str:
    """Get the current model name for logging."""
    config = get_model_config()
    # Return the full model name with provider prefix for compatibility
    return config.get("full_model", f"{config['provider']}/{config['model_name']}")


def create_gemini_settings(settings: Dict[str, Any]) -> GoogleModelSettings:
    """Create GoogleModelSettings from config dict."""
    # Use constants for defaults
    defaults = DEFAULT_MODEL_SETTINGS["gemini"].copy()
    
    # Merge user settings with defaults
    merged_settings = {**defaults, **settings}
    
    # Handle thinking config - convert thinking_budget to google_thinking_config format
    thinking_budget = merged_settings.pop("thinking_budget", defaults["thinking_budget"])
    merged_settings["google_thinking_config"] = {"thinking_budget": thinking_budget}
    
    logger.info(f"Creating Gemini settings: max_tokens={merged_settings.get('max_tokens')}, temperature={merged_settings.get('temperature')}, thinking_budget={thinking_budget}")
    return GoogleModelSettings(**merged_settings)


def create_openai_settings(settings: Dict[str, Any]) -> OpenAIModelSettings:
    """Create OpenAIModelSettings from config dict."""
    # Use constants for defaults
    defaults = DEFAULT_MODEL_SETTINGS["openai"].copy()
    
    merged_settings = {**defaults, **settings}
    logger.info(f"Creating OpenAI settings: max_tokens={merged_settings.get('max_tokens')}, temperature={merged_settings.get('temperature')}")
    return OpenAIModelSettings(**merged_settings)


def initialize_model_config():
    """Initialize model configuration and create model instance. Must be called once at startup."""
    global _cached_model
    
    config = get_model_config()
    
    # Log configuration details once
    if config.get("provider") == "openai" and "OPENAI_BASE_URL" in os.environ:
        logger.info(f"Set OPENAI_BASE_URL to {os.environ['OPENAI_BASE_URL']}")
    
    logger.info(f"Loaded configuration: {config.get('full_model', 'unknown')} from {config.get('provider', 'unknown')}")
    
    # Create model based on provider
    if config.get("provider") == "gemini":
        # Get API key from environment
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable is required for Gemini models")
        
        logger.info(f"Using Gemini model: {config['model_name']}")
        provider = GoogleProvider(api_key=api_key)
        
        # Create model settings
        model_settings = create_gemini_settings(config.get("model_settings", {}))
        _cached_model = GoogleModel(config["model_name"], provider=provider, settings=model_settings)
    else:
        # Default to OpenAI-compatible models
        api_key = os.environ.get("OPENAI_API_KEY", "dummy")
        
        # Create and cache the model
        logger.info(f"Using model: {config['model_name']} at {config['base_url']}")
        provider = OpenAIProvider(base_url=config["base_url"], api_key=api_key)
        
        # Create model settings
        model_settings = create_openai_settings(config.get("model_settings", {}))
        _cached_model = OpenAIModel(config["model_name"], provider=provider, settings=model_settings)
