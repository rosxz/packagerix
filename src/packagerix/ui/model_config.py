"""Model configuration flow for packagerix using LiteLLM."""

import os
import litellm
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from packagerix.ui.logging_config import logger


@dataclass
class Provider:
    """Model provider configuration."""
    name: str
    display_name: str
    env_var: str
    requires_api_key: bool
    setup_url: str


# Define available providers
PROVIDERS = [
    Provider(
        name="anthropic",
        display_name="Anthropic (Claude)",
        env_var="ANTHROPIC_API_KEY",
        requires_api_key=True,
        setup_url="https://console.anthropic.com/"
    ),
    Provider(
        name="openai",
        display_name="OpenAI (GPT)",
        env_var="OPENAI_API_KEY", 
        requires_api_key=True,
        setup_url="https://platform.openai.com/"
    ),
    Provider(
        name="google",
        display_name="Gemini",
        env_var="GEMINI_API_KEY",
        requires_api_key=True,
        setup_url="https://makersuite.google.com/"
    ),
    Provider(
        name="ollama",
        display_name="Ollama (Local)",
        env_var="OLLAMA_BASE_URL",
        requires_api_key=False,
        setup_url="https://ollama.ai/"
    )
]


# Model configuration is now handled through UI-specific dialogs
# Use the appropriate UI implementation to configure models


# These functions have been moved to UI-specific implementations


def get_available_models(provider: Provider) -> List[str]:
    """Get available models for a provider."""
    try:
        # Use LiteLLM's get_valid_models with provider-specific endpoint checking
        models = litellm.utils.get_valid_models(
            check_provider_endpoint=True, 
            custom_llm_provider=provider.name
        )
        
        # Add provider prefix to all models for LiteLLM
        if provider.name == "ollama":
            return [f"ollama/{model}" for model in models]
        elif provider.name == "google":
            return [f"gemini/{model}" for model in models]
        else:
            # Anthropic and OpenAI models typically don't need prefixes
            return models
    except Exception as e:
        logger.warning(f"Could not fetch models for {provider.name}: {e}")
        return []


def validate_configuration(provider: Provider, model: str) -> bool:
    """Validate the model configuration.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        # Try to check if the key is valid
        if provider.requires_api_key:
            key_valid = litellm.check_valid_key(
                model=model,
                api_key=os.environ.get(provider.env_var)
            )
            if not key_valid:
                logger.warning(f"API key validation failed for {provider.display_name}")
                return False
        
        # Try a simple completion to validate
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Say 'hello'"}],
            max_tokens=10
        )
        
        logger.info("Configuration validated successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        return False


def save_configuration(provider: Provider, model: str):
    """Save the configuration for future use."""
    # Set environment variables for magentic
    os.environ["MAGENTIC_BACKEND"] = "litellm"
    os.environ["MAGENTIC_LITELLM_MODEL"] = model
    
    # Save to a config file for persistence
    config_data = {
        "provider": provider.name,
        "model": model,
        "backend": "litellm"
    }
    
    try:
        import json
        config_path = os.path.expanduser("~/.packagerix/config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Configuration saved to {config_path}")
    except Exception as e:
        logger.warning(f"Could not save configuration: {e}")


def load_saved_configuration() -> Optional[Tuple[str, str]]:
    """Load previously saved configuration."""
    try:
        import json
        config_path = os.path.expanduser("~/.packagerix/config.json")
        
        if os.path.exists(config_path):
            with open(config_path) as f:
                config_data = json.load(f)
            
            # Find the provider
            provider_name = config_data.get("provider")
            model = config_data.get("model")
            
            if provider_name and model:
                # Set environment variables
                os.environ["MAGENTIC_BACKEND"] = "litellm"
                os.environ["MAGENTIC_LITELLM_MODEL"] = model
                
                # Load API keys from secure storage if needed
                provider = next((p for p in PROVIDERS if p.name == provider_name), None)
                if provider and provider.requires_api_key:
                    from packagerix.secure_keys import get_api_key
                    api_key = get_api_key(provider.env_var)
                    if api_key:
                        os.environ[provider.env_var] = api_key
                        logger.info(f"Loaded API key for {provider.display_name} from secure storage")
                
                logger.info(f"Loaded saved configuration: {model} from {provider_name}")
                return provider_name, model
    
    except Exception as e:
        logger.warning(f"Could not load saved configuration: {e}")
    
    return None


# The ensure_model_configured function is now implemented by UI-specific code