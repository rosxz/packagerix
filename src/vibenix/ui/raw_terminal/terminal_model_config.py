"""Terminal-based model configuration for pydantic-ai."""

import os
import requests
from typing import Optional, Dict, Any, List
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


def choose_provider_terminal() -> Optional[str]:
    """Let user choose between providers."""
    print("\n🔧 Choose AI Provider:")
    print("1. OpenAI-compatible (local models, OpenAI, etc.)")
    print("2. Google Gemini")
    
    while True:
        choice = input("\nSelect provider (1-2) or 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            return None
        elif choice == '1':
            return "openai"
        elif choice == '2':
            return "gemini"
        else:
            print("❌ Please enter 1, 2, or 'q' to quit")


def get_available_gemini_models(api_key: str) -> List[str]:
    """Get available Gemini models from Google API."""
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        headers = {}
        params = {"key": api_key}
        
        logger.info(f"Querying Google API for available models")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        models = []
        
        # Filter models that support generateContent
        for model_data in data.get("models", []):
            model_name = model_data.get("name", "")
            supported_actions = model_data.get("supportedGenerationMethods", [])
            
            if "generateContent" in supported_actions:
                # Extract model ID from full name (e.g., "models/gemini-1.5-flash" -> "gemini-1.5-flash")
                if "/" in model_name:
                    model_id = model_name.split("/")[-1]
                    models.append(model_id)
        
        logger.info(f"Retrieved {len(models)} Gemini models from Google API")
        return models
    except Exception as e:
        logger.warning(f"Failed to query Google models API: {e}")
        # Return fallback models if API fails
        return [
            "gemini-1.5-flash",
            "gemini-1.5-pro", 
            "gemini-2.5-flash",
            "gemini-2.5-pro"
        ]


def configure_model_settings(provider: str) -> Dict[str, Any]:
    """Allow user to configure model settings for the selected provider."""
    defaults = DEFAULT_MODEL_SETTINGS.get(provider, DEFAULT_MODEL_SETTINGS["openai"])
    
    print(f"\n⚙️  Model Settings for {provider.title()}")
    print("=" * 40)
    
    # Show current defaults
    print("Default settings:")
    for key, value in defaults.items():
        print(f"  • {key}: {value}")
    
    use_defaults = input(f"\nUse defaults? (Y/n): ").strip().lower()
    if use_defaults != 'n':
        return defaults.copy()
    
    print("\n🔧 Customize Settings:")
    custom_settings = {}
    
    # Configure each setting generically
    for key, default_value in defaults.items():
        while True:
            try:
                user_input = input(f"{key} (default {default_value}): ").strip()
                if not user_input:
                    custom_settings[key] = default_value
                    break
                
                # Try to convert to the same type as default
                if isinstance(default_value, bool):
                    custom_settings[key] = user_input.lower() in ('true', 't', 'yes', 'y', '1')
                elif isinstance(default_value, int):
                    custom_settings[key] = int(user_input)
                elif isinstance(default_value, float):
                    custom_settings[key] = float(user_input)
                else:
                    custom_settings[key] = user_input
                break
            except ValueError:
                print("❌ Invalid input, try again")
    
    return custom_settings


def choose_gemini_model_terminal() -> Optional[str]:
    """Let user choose a Gemini model."""
    # Check if GOOGLE_API_KEY is set
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("\n⚠️  GOOGLE_API_KEY environment variable not found!")
        print("Please set your Google API key:")
        print("export GOOGLE_API_KEY=your_api_key_here")
        print("\nGet your API key from: https://aistudio.google.com")
        return None
    
    print("\n🤔 Fetching available Gemini models...")
    gemini_models = get_available_gemini_models(api_key)
    
    if not gemini_models:
        print("\n⚠️  No models found. Using manual entry:")
        model = input("Enter Gemini model name (e.g., gemini-1.5-flash): ").strip()
        return model if model else None
    
    print(f"\n🧠 Available Gemini Models ({len(gemini_models)}):")
    for i, model in enumerate(gemini_models, 1):
        print(f"{i}. {model}")
    
    while True:
        choice = input(f"\nSelect model (1-{len(gemini_models)}) or 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            return None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(gemini_models):
                return gemini_models[idx]
            else:
                print(f"❌ Please enter a number between 1 and {len(gemini_models)}")
        except ValueError:
            print("❌ Please enter a valid number or 'q' to quit")


def show_model_config_terminal() -> Optional[Dict[str, str]]:
    """Show terminal-based model configuration dialog.
    
    Returns:
        Dict with 'provider', 'model', and optionally 'openai_api_base' keys, or None if cancelled
    """
    print("\n🤖 Configure AI Model")
    print("=" * 50)
    
    # Choose provider
    provider = choose_provider_terminal()
    if not provider:
        return None
    
    if provider == "gemini":
        # Handle Gemini configuration
        model = choose_gemini_model_terminal()
        if not model:
            return None
        
        # Configure model settings
        model_settings = configure_model_settings(provider)
        
        # Save configuration
        print(f"\n✅ Saving configuration: {model}")
        save_configuration(provider, model, None, model_settings)
        
        return {
            "provider": provider,
            "model": f"{provider}/{model}"
        }
    else:
        # Handle OpenAI-compatible configuration
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
        
        # Configure model settings
        model_settings = configure_model_settings(provider)
        
        # Save configuration
        print(f"\n✅ Saving configuration: {model}")
        save_configuration(provider, model, openai_api_base, model_settings)
        
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
                return input


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


def save_configuration(provider: str, model: str, openai_api_base: str, model_settings: Dict[str, Any] = None):
    """Save the configuration for future use."""
    # Use default model settings if none provided
    if model_settings is None:
        model_settings = DEFAULT_MODEL_SETTINGS.get(provider, DEFAULT_MODEL_SETTINGS["openai"])
    
    # Save to config file
    config_data = {
        "provider": provider,
        "model": f"{provider}/{model}",
        "backend": "pydantic-ai",
        "openai_api_base": openai_api_base,
        "model_settings": model_settings
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
        provider_name, model, ollama_host, openai_api_base, model_settings = saved_config
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
