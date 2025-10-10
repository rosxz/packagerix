"""Terminal-based model configuration for pydantic-ai."""

import os
import requests
from typing import Optional, Dict, Any, List
from vibenix.ui.logging_config import logger


def get_available_models_from_endpoint(base_url: str, api_key: str = "dummy") -> List[str]:
    """Get available models from OpenAI-compatible endpoint."""
    try:
        headers = {}
        if api_key and api_key != "dummy":
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Ensure base URL ends with /v1
        if not base_url.endswith("/v1/") and not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1/"
        
        models_url = base_url.rstrip("/") + "/models"
        logger.info(f"Querying {models_url} for available models")
        
        response = requests.get(models_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        models = [model["id"] for model in data.get("data", [])]
        logger.info(f"Retrieved {len(models)} models from {models_url}")
        return models
    except Exception as e:
        logger.warning(f"Failed to query models endpoint: {e}")
        return []


def show_model_config_terminal() -> Optional[Dict[str, str]]:
    """Show terminal-based model configuration dialog.
    
    Returns:
        Dict with 'provider', 'model', and optionally 'openai_api_base' keys, or None if cancelled
    """
    print("\n🤖 Configure AI Model")
    print("=" * 50)
    
    # For now, we only support OpenAI-compatible endpoints
    provider = "openai"
    print(f"\n✅ Using OpenAI-compatible API")
    
    # Get the base URL
    openai_api_base = handle_openai_api_base_terminal()
    if not openai_api_base:
        # Use default if not provided
        openai_api_base = "http://llama.digidow.ins.jku.at:11434/v1/"
    
    # Get API key from environment or use dummy
    api_key = os.environ.get("OPENAI_API_KEY", "dummy")
    
    # Choose model
    model = choose_model_terminal(openai_api_base, api_key)
    if not model:
        return None
    
    # Save configuration
    print(f"\n✅ Saving configuration: {model}")
    
    # Save to config file
    save_configuration(provider, model, openai_api_base)
    
    return {
        "provider": provider,
        "model": f"{provider}/{model}",
        "openai_api_base": openai_api_base
    }


def handle_openai_api_base_terminal() -> Optional[str]:
    """Handle OpenAI API base URL configuration."""
    print("\n📍 OpenAI API Base URL Configuration")
    print("Enter the base URL for your OpenAI-compatible API")
    print("(Press Enter to use default: http://llama.digidow.ins.jku.at:11434/v1/)")
    
    while True:
        api_base = input("\nAPI Base URL: ").strip()
        
        if not api_base:
            # Use default
            return None
        
        # Basic validation
        if not api_base.startswith(("http://", "https://")):
            print("❌ URL must start with http:// or https://")
            continue
        
        # Test the endpoint
        print(f"\n🔍 Testing connection to {api_base}...")
        try:
            # Ensure it ends with /v1/
            test_url = api_base
            if not test_url.endswith("/v1/") and not test_url.endswith("/v1"):
                test_url = test_url.rstrip("/") + "/v1/"
            
            response = requests.get(test_url + "models", timeout=5)
            response.raise_for_status()
            print("✅ Successfully connected!")
            return api_base
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            retry = input("\nRetry with different URL? (y/N): ").strip().lower()
            if retry != 'y':
                return None


def choose_model_terminal(base_url: str, api_key: str) -> Optional[str]:
    """Let user choose a model from available options."""
    print("\n🤔 Fetching available models...")
    
    models = get_available_models_from_endpoint(base_url, api_key)
    
    if not models:
        print("\n⚠️  No models found via API. Enter model name manually:")
        model = input("Model name: ").strip()
        return model if model else None
    
    print(f"\n📋 Available models ({len(models)}):")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model}")
    
    while True:
        choice = input(f"\nSelect model (1-{len(models)}) or 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            return None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
            else:
                print(f"❌ Please enter a number between 1 and {len(models)}")
        except ValueError:
            print("❌ Please enter a valid number or 'q' to quit")


def save_configuration(provider: str, model: str, openai_api_base: str):
    """Save the configuration for future use."""
    # Save to config file
    config_data = {
        "provider": provider,
        "model": f"{provider}/{model}",
        "backend": "pydantic-ai",
        "openai_api_base": openai_api_base
    }
    
    try:
        import json
        config_path = os.path.expanduser("~/.vibenix/config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Configuration saved to {config_path}")
    except Exception as e:
        logger.warning(f"Could not save configuration: {e}")


def ensure_model_configured() -> bool:
    """Ensure model is configured for terminal mode.
    
    Returns:
        True if model is configured, False if user cancelled
    """
    # First try to load saved configuration
    from vibenix.model_config import load_saved_configuration
    saved_config = load_saved_configuration()
    
    if saved_config:
        provider_name, model, ollama_host, openai_api_base = saved_config
        print(f"\n✅ Found saved model configuration: {model}")
        
        # Ask if they want to use it or reconfigure
        use_saved = input("Use this configuration? (Y/n): ").strip().lower()
        if use_saved != 'n':
            return True
    
    # No saved config or user wants to reconfigure
    print("\n⚙️  Let's configure your AI model")
    
    config = show_model_config_terminal()
    if config:
        print("\n✅ Model configuration complete!")
        return True
    else:
        print("\n❌ Configuration cancelled")
        return False