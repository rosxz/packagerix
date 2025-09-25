"""Model configuration for pydantic-ai integration.

This module provides hardcoded model configurations for Ollama.
"""

import os
from typing import Optional
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider


def get_model_config() -> dict:
    """Get the hardcoded model configuration."""
    return {
        "provider": "openai",
        "model_name": "gpt-oss-120b",
        "base_url": "http://llama.digidow.ins.jku.at:11434/v1/"
    }


def create_model():
    """Create a pydantic-ai model instance with Ollama provider."""
    config = get_model_config()
    
    provider = OpenAIProvider(base_url=config["base_url"], api_key="dummy")
    model = OpenAIModel(config["model_name"], provider=provider)
    
    return model


def get_model_name() -> str:
    """Get the current model name for logging."""
    config = get_model_config()
    return f"{config['provider']}/{config['model_name']}"
