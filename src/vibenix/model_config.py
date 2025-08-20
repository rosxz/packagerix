"""Model configuration for pydantic-ai integration.

This module provides hardcoded model configurations for Ollama.
"""

import os
from typing import Optional
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.ollama import OllamaProvider


def get_model_config() -> dict:
    """Get the hardcoded model configuration."""
    return {
        "provider": "ollama",
        "model_name": "qwen3-coder:30b-a3b-q4_K_M_131768ctx",
        "base_url": os.getenv("OLLAMA_HOST", "https://hydralisk.van-duck.ts.net:11435") + "/v1"
    }


def create_model():
    """Create a pydantic-ai model instance with Ollama provider."""
    config = get_model_config()
    
    provider = OllamaProvider(base_url=config["base_url"])
    model = OpenAIModel(config["model_name"], provider=provider)
    
    return model


def get_model_name() -> str:
    """Get the current model name for logging."""
    config = get_model_config()
    return f"{config['provider']}/{config['model_name']}"
