"""Pytest configuration for packagerix tests."""

import pytest
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def model_config():
    """Set up model configuration using the app's initialization logic."""
    from packagerix.ui.model_config import load_saved_configuration
    
    config = load_saved_configuration()
    if not config:
        raise RuntimeError("No model configuration found. Run 'packagerix' to configure a model first.")
    
    provider_name, model, ollama_host = config
    return {
        "provider": provider_name,
        "model": model,
        "ollama_host": ollama_host
    }