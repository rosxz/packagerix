"""Model configuration flow for vibenix using LiteLLM."""

import os
import litellm
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from vibenix.ui.logging_config import logger


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
        name="gemini",
        display_name="Gemini",
        env_var="GEMINI_API_KEY",
        requires_api_key=True,
        setup_url="https://aistudio.google.com/"
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
    # Special handling for OpenAI provider with custom base URL
    if provider.name == "openai" and os.environ.get("OPENAI_BASE_URL"):
        try:
            import requests
            base_url = os.environ.get("OPENAI_BASE_URL").rstrip('/')
            headers = {}
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            logger.info(f"Querying {base_url}/models for available models")
            response = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            models = [model["id"] for model in data.get("data", [])]
            logger.info(f"Retrieved {len(models)} models from {base_url}/models")
            # Return with openai/ prefix for use with LiteLLM
            return [f"openai/{model}" for model in models]
        except Exception as e:
            logger.warning(f"Failed to query custom OpenAI endpoint: {e}")
            return []
    
    # Standard flow for other providers
    try:
        # Ensure OPENAI_API_KEY is set to empty string if not present for OpenAI provider
        if provider.name == "openai" and "OPENAI_API_KEY" not in os.environ:
            os.environ["OPENAI_API_KEY"] = ""
            
        # Build litellm_params based on provider
        litellm_params = None
        if provider.name == "ollama" and os.environ.get("OLLAMA_API_BASE"):
            from litellm import LiteLLM_Params
            # Use a dummy model name for discovery
            litellm_params = LiteLLM_Params(
                model="ollama/dummy",
                api_base=os.environ.get("OLLAMA_API_BASE")
            )
            logger.info(f"Using Ollama API base: {os.environ.get('OLLAMA_API_BASE')}")
        
        # Use LiteLLM's get_valid_models with provider-specific endpoint checking
        models = litellm.utils.get_valid_models(
            check_provider_endpoint=True, 
            custom_llm_provider=provider.name,
            litellm_params=litellm_params
        )
        
        # Add provider prefix to all models for LiteLLM
        if provider.name == "ollama":
            return [f"ollama/{model}" for model in models]
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


def save_configuration(provider: Provider, model: str, ollama_host: Optional[str] = None, openai_api_base: Optional[str] = None):
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
    
    # Always save ollama_host if provided, regardless of current provider
    if ollama_host:
        config_data["ollama_host"] = ollama_host
    
    # Always save openai_api_base if provided, regardless of current provider
    if openai_api_base:
        config_data["openai_api_base"] = openai_api_base
    
    # Only set OLLAMA_API_BASE if we're actually using Ollama
    if provider.name == "ollama" and ollama_host:
        os.environ["OLLAMA_API_BASE"] = ollama_host
        logger.info(f"Set OLLAMA_API_BASE to {ollama_host}")
    
    # Only set OPENAI_BASE_URL if we're actually using OpenAI
    if provider.name == "openai" and openai_api_base:
        os.environ["OPENAI_BASE_URL"] = openai_api_base
        logger.info(f"Set OPENAI_BASE_URL to {openai_api_base}")
    
    try:
        import json
        config_path = os.path.expanduser("~/.vibenix/config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Configuration saved to {config_path}")
    except Exception as e:
        logger.warning(f"Could not save configuration: {e}")


def load_saved_configuration() -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
    """Load previously saved configuration, returns (provider_name, model, ollama_host, openai_api_base)."""
    try:
        import json
        config_path = os.path.expanduser("~/.vibenix/config.json")
        
        if os.path.exists(config_path):
            with open(config_path) as f:
                config_data = json.load(f)
            
            # Find the provider
            provider_name = config_data.get("provider")
            model = config_data.get("model")
            ollama_host = config_data.get("ollama_host")
            openai_api_base = config_data.get("openai_api_base")
            
            if provider_name and model:
                # Set environment variables
                os.environ["MAGENTIC_BACKEND"] = "litellm"
                os.environ["MAGENTIC_LITELLM_MODEL"] = model
                
                # Load API keys from secure storage if needed
                provider = next((p for p in PROVIDERS if p.name == provider_name), None)
                if provider and provider.requires_api_key:
                    from vibenix.secure_keys import get_api_key
                    api_key = get_api_key(provider.env_var)
                    if api_key:
                        os.environ[provider.env_var] = api_key
                        logger.info(f"Loaded API key for {provider.display_name} from secure storage")
                
                # Set OLLAMA_API_BASE only if using Ollama
                if provider_name == "ollama" and ollama_host:
                    os.environ["OLLAMA_API_BASE"] = ollama_host
                    logger.info(f"Set OLLAMA_API_BASE to {ollama_host}")
                
                # Set OPENAI_BASE_URL only if using OpenAI
                if provider_name == "openai" and openai_api_base:
                    os.environ["OPENAI_BASE_URL"] = openai_api_base
                    logger.info(f"Set OPENAI_BASE_URL to {openai_api_base}")
                
                logger.info(f"Loaded saved configuration: {model} from {provider_name}")
                return provider_name, model, ollama_host, openai_api_base
    
    except Exception as e:
        logger.warning(f"Could not load saved configuration: {e}")
    
    return None


# The ensure_model_configured function is now implemented by UI-specific code
