"""Terminal-based model configuration for pydantic-ai."""

import os
import requests
from typing import Optional, Dict, Any, List
from vibenix.ui.logging_config import logger

from vibenix.model_config import DEFAULT_MODEL_SETTINGS
PROVIDERS = DEFAULT_MODEL_SETTINGS.keys()

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
    print("2. Anthropic")
    print("3. Google Gemini")
    
    while True:
        choice = input("\nSelect provider (1-3) or 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            return None
        elif choice == '1':
            return "openai"
        elif choice == '2':
            return "anthropic"
        elif choice == '3':
            return "gemini"
        else:
            print("❌ Please enter 1, 2, 3, or 'q' to quit")


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
    # Check if GEMINI_API_KEY or GOOGLE_API_KEY is set
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("\n⚠️  GEMINI_API_KEY or GOOGLE_API_KEY environment variable not found!")
        print("Please set your Google API key:")
        print("export GEMINI_API_KEY=your_api_key_here")
        print("\nGet your API key from: https://aistudio.google.com")
        return None
    
    print("\n🤔 Fetching available Gemini models...")
    gemini_models = get_gemini_models(api_key)
    
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
    
    # Step 1: Choose provider
    provider = choose_provider_terminal()
    if not provider:
        return None
    
    # Step 2: Handle provider-specific configuration
    openai_api_base = None
    api_key = None
    
    if provider == "openai":
        # Get the base URL for OpenAI-compatible endpoints
        openai_api_base = handle_openai_api_base_terminal()
        if not openai_api_base:
            # Use default if not provided
            openai_api_base = "http://llama.digidow.ins.jku.at:11434/v1/"
        api_key = os.environ.get("OPENAI_API_KEY", "dummy")
    elif provider == "anthropic":
        # Handle Anthropic API key
        if not handle_api_key_terminal("ANTHROPIC_API_KEY", "Anthropic", "https://console.anthropic.com/"):
            return None
        # Get the API key for model selection
        from vibenix.secure_keys import get_api_key
        api_key = os.environ.get("ANTHROPIC_API_KEY") or get_api_key("ANTHROPIC_API_KEY")
        if not api_key:
            print("\n❌ Failed to retrieve API key")
            return None
    elif provider == "gemini":
        # Handle Gemini API key
        if not handle_api_key_terminal("GEMINI_API_KEY", "Gemini", "https://aistudio.google.com/"):
            return None
        # Get the API key for model selection
        from vibenix.secure_keys import get_api_key
        api_key = os.environ.get("GEMINI_API_KEY") or get_api_key("GEMINI_API_KEY")
        if not api_key:
            print("\n❌ Failed to retrieve API key")
            return None
    else:
        print(f"\n❌ Unknown provider: {provider}")
        return None
    
    # Step 3: Choose model
    if provider == "openai":
        model = choose_model_terminal(openai_api_base, api_key)
    elif provider == "anthropic":
        model = choose_anthropic_model_terminal(api_key)
    elif provider == "gemini":
        model = choose_gemini_model_terminal(api_key)
    
    if not model:
        return None
    
    # Step 4: Configure model settings
    model_settings = configure_model_settings(provider)
    
    # Save configuration
    print(f"\n✅ Saving configuration: {provider}/{model}")
    
    # Save to config file
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


def handle_api_key_terminal(key_name: str, provider_name: str, setup_url: str) -> bool:
    """Handle API key input for terminal."""
    from vibenix.secure_keys import get_api_key, set_api_key
    
    # Check if we already have a key in secure storage
    existing_key = get_api_key(key_name)
    
    # Check environment variable (as override, don't save)
    env_key = os.environ.get(key_name)
    
    if env_key:
        print(f"\nUsing {key_name} from environment variable")
        return True
    
    if existing_key:
        print(f"\nAPI key for {provider_name} is already configured.")
        use_existing = input("Use existing key? (Y/n): ").strip().lower()
        if use_existing != 'n':
            return True
    
    # Get new API key
    print(f"\nAPI Key for {provider_name}")
    print(f"Get your key from: {setup_url}")
    
    try:
        import getpass
        api_key = getpass.getpass("Enter API key (input hidden): ").strip()
        
        if not api_key:
            print("❌ No API key provided")
            return False
        
        # Store in secure storage
        set_api_key(key_name, api_key)
        print(f"✅ API key saved securely")
        return True
        
    except (KeyboardInterrupt, EOFError):
        print("\n❌ API key input cancelled")
        return False


def get_anthropic_models(api_key: str) -> List[str]:
    """Query available Anthropic models from their API."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    
    # List all available models
    models_page = client.models.list()
    models = [model.id for model in models_page.data]
    
    logger.info(f"Retrieved {len(models)} Anthropic models")
    return models


def get_gemini_models(api_key: str) -> List[str]:
    """Query available Gemini models from Google's API."""
    from google import genai
    
    # Create client with API key
    client = genai.Client(api_key=api_key)
    
    # Get models that support generateContent
    models = []
    for model in client.models.list():
        if "generateContent" in model.supported_actions:
            # Extract model name without the "models/" prefix
            model_name = model.name.replace("models/", "")
            models.append(model_name)
    
    logger.info(f"Retrieved {len(models)} Gemini models")
    return models


def choose_anthropic_model_terminal(api_key: str) -> Optional[str]:
    """Let user choose an Anthropic model."""
    print("\n🔍 Fetching available Anthropic models...")
    models = get_anthropic_models(api_key)
    
    if not models:
        print("\n⚠️  Could not retrieve models. Enter model name manually:")
        model = input("Model name: ").strip()
        return model if model else None
    
    print(f"\n📋 Available Anthropic models ({len(models)}):")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model}")
    print(f"{len(models) + 1}. Enter custom model name")
    
    while True:
        choice = input(f"\nSelect model (1-{len(models)+1}) or 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            return None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
            elif idx == len(models):
                model = input("Enter model name: ").strip()
                return model if model else None
            else:
                print(f"❌ Please enter a number between 1 and {len(models)+1}")
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
