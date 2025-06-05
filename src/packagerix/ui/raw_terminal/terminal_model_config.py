"""Terminal-based model configuration that mirrors the textual UI."""

import os
from typing import Optional, Dict, Any
from packagerix.ui.model_config import PROVIDERS, Provider, get_available_models, save_configuration, load_saved_configuration
from packagerix.ui.textual.model_config_dialog import check_api_key_valid
from packagerix.ui.logging_config import logger


def show_model_config_terminal() -> Optional[Dict[str, str]]:
    """Show terminal-based model configuration dialog.
    
    Returns:
        Dict with 'provider' and 'model' keys, or None if cancelled
    """
    print("\n🤖 Configure AI Model")
    print("=" * 50)
    
    # Step 1: Choose provider
    provider = choose_provider_terminal()
    if not provider:
        return None
    
    # Step 2: Handle API key if needed
    if provider.requires_api_key:
        if not handle_api_key_terminal(provider):
            return None
    
    # Step 3: Choose model
    model = choose_model_terminal(provider)
    if not model:
        return None
    
    # Step 4: Save configuration
    print(f"\n✅ Saving configuration: {model} from {provider.display_name}")
    
    # Set environment variables
    os.environ["MAGENTIC_BACKEND"] = "litellm"
    os.environ["MAGENTIC_LITELLM_MODEL"] = model
    
    # Save to config file and secure storage
    save_configuration(provider, model)
    
    return {
        "provider": provider.name,
        "model": model
    }


def choose_provider_terminal() -> Optional[Provider]:
    """Let user choose a provider in terminal."""
    print("\nSelect Provider:")
    
    # Show providers with status
    for i, provider in enumerate(PROVIDERS, 1):
        display_name = provider.display_name
        if check_api_key_valid(provider):
            display_name += " [valid key configured]"
        print(f"{i}. {display_name}")
    
    while True:
        try:
            choice = input(f"\nEnter choice (1-{len(PROVIDERS)}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            index = int(choice) - 1
            if 0 <= index < len(PROVIDERS):
                return PROVIDERS[index]
            else:
                print(f"Invalid choice. Please enter a number between 1 and {len(PROVIDERS)}")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nCancelled")
            return None


def handle_api_key_terminal(provider: Provider) -> bool:
    """Handle API key input for terminal."""
    # Check if we already have a valid key
    if check_api_key_valid(provider):
        use_existing = input(f"\nAPI key for {provider.display_name} is already configured. Use it? (y/n): ").strip().lower()
        if use_existing in ['y', 'yes', '']:
            return True
    
    # Get new API key
    print(f"\nAPI Key required for {provider.display_name}")
    print(f"Get your key from: {provider.setup_url}")
    
    try:
        import getpass
        api_key = getpass.getpass("Enter API key (input hidden): ").strip()
        
        if not api_key:
            print("No API key entered")
            return False
        
        # Save to secure storage
        from packagerix.secure_keys import set_api_key
        set_api_key(provider.env_var, api_key)
        
        # Set in environment for current session
        os.environ[provider.env_var] = api_key
        
        print("✅ API key saved")
        return True
        
    except KeyboardInterrupt:
        print("\nCancelled")
        return False


def choose_model_terminal(provider: Provider) -> Optional[str]:
    """Choose a model from provider in terminal."""
    print(f"\nLoading available models for {provider.display_name}...")
    
    try:
        available_models = get_available_models(provider)
        
        if not available_models:
            print(f"❌ Failed to load models for {provider.display_name}")
            print("This indicates an implementation error with model discovery.")
            return None
        
        # Show available models
        print(f"\nAvailable models:")
        for i, model in enumerate(available_models[:20], 1):  # Show up to 20 models
            print(f"{i}. {model}")
        
        while True:
            try:
                choice = input(f"\nEnter choice (1-{len(available_models)}) or 'q' to quit: ").strip()
                
                if choice.lower() == 'q':
                    return None
                
                index = int(choice) - 1
                if 0 <= index < len(available_models):
                    return available_models[index]
                else:
                    print(f"Invalid choice. Please enter a number between 1 and {len(available_models)}")
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nCancelled")
                return None
                
    except Exception as e:
        print(f"❌ Error loading models: {e}")
        return None


def ensure_model_configured() -> bool:
    """Ensure model is configured for terminal mode.
    
    Returns:
        True if model is configured, False if user cancelled
    """
    # First try to load saved configuration
    saved_config = load_saved_configuration()
    
    if saved_config:
        provider_name, model = saved_config
        print(f"\n✅ Found saved model configuration: {model}")
        use_saved = input("Use this configuration? (Y/n): ").strip().lower()
        
        if use_saved in ['', 'y', 'yes']:
            print(f"✅ Using saved model configuration: {model}")
            return True
        # Otherwise fall through to configuration dialog
    
    # Show configuration dialog
    result = show_model_config_terminal()
    
    if result:
        print(f"✅ Model configured: {result['model']}")
        return True
    else:
        print("❌ Model configuration required to continue")
        return False