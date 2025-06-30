"""Model configuration dialog for Textual UI."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Select, Input, Label, ListView, ListItem
from textual.containers import Vertical, Horizontal
from typing import Optional, List
import os
import asyncio
import litellm
from vibenix.ui.model_config import PROVIDERS, Provider, get_available_models, save_configuration
from vibenix.ui.logging_config import logger


def check_api_key_valid(provider: Provider) -> bool:
    """Check if the API key for a provider is valid."""
    if not provider.requires_api_key:
        return True
    
    # Check environment variable first
    api_key = os.environ.get(provider.env_var)
    
    # If not in environment, check secure storage
    if not api_key:
        from vibenix.secure_keys import get_api_key
        api_key = get_api_key(provider.env_var)
        if api_key:
            # Set in environment for this session
            os.environ[provider.env_var] = api_key
    
    if not api_key:
        return False
    
    try:
        # Try to get models from the provider endpoint - this validates the API key
        models = litellm.utils.get_valid_models(
            check_provider_endpoint=True,
            custom_llm_provider=provider.name
        )
        return len(models) > 0
    except:
        return False


class ModelConfigDialog(ModalScreen):
    """Modal dialog for configuring the AI model."""
    
    CSS = """
    ModelConfigDialog {
        align: center middle;
    }
    
    #config-dialog {
        width: 80;
        height: auto;
        min-height: 20;
        max-height: 40;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #dialog-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    
    .config-section {
        margin: 1 0;
    }
    
    .hidden {
        display: none;
    }
    
    .config-label {
        margin-bottom: 0;
    }
    
    Select {
        margin: 0 0 1 0;
    }
    
    ListView {
        height: 8;
        margin: 0 0 1 0;
        border: solid $primary;
    }
    
    Input {
        margin: 0 0 1 0;
    }
    
    #button-container {
        height: 3;
        align: center middle;
        margin-top: 2;
    }
    
    Button {
        margin: 0 1;
        min-width: 12;
    }
    
    #status-message {
        text-align: center;
        margin: 1 0;
    }
    
    .error {
        color: $error;
    }
    
    .success {
        color: $success;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.selected_provider = None
        self.selected_model = None
        
        # Load saved configuration if available
        from vibenix.ui.model_config import load_saved_configuration
        saved_config = load_saved_configuration()
        if saved_config:
            if len(saved_config) == 3:  # New format with ollama_host
                provider_name, model, ollama_host = saved_config
                self.saved_ollama_host = ollama_host
            else:  # Old format compatibility
                provider_name, model = saved_config
                self.saved_ollama_host = None
            self.saved_provider = provider_name
            self.saved_model = model
        else:
            self.saved_provider = None
            self.saved_model = None
            self.saved_ollama_host = None
        
    def compose(self) -> ComposeResult:
        """Create the configuration dialog layout."""
        with Vertical(id="config-dialog"):
            yield Static("🤖 Configure AI Model", id="dialog-title")
            
            # Provider selection
            with Vertical(classes="config-section"):
                yield Label("Select Provider:", classes="config-label")
                provider_options = []
                for p in PROVIDERS:
                    display_name = p.display_name
                    if check_api_key_valid(p):
                        display_name += " [valid key configured]"
                    provider_options.append((display_name, p.name))
                
                yield Select(
                    options=provider_options,
                    prompt="Choose a provider",
                    id="provider-select"
                )
            
            # API key input (hidden by default)
            with Vertical(id="api-key-section", classes="config-section hidden"):
                yield Label("API Key:", classes="config-label", id="api-key-label")
                yield Input(
                    placeholder="Enter your API key",
                    password=True,
                    id="api-key-input"
                )
            
            # Model selection
            with Vertical(id="model-section", classes="config-section hidden"):
                yield Label("Select Model:", classes="config-label")
                yield ListView(id="model-list")
                
            # Ollama host configuration (only shown for Ollama)
            with Vertical(id="ollama-section", classes="config-section hidden"):
                yield Label("Ollama Host (optional):", classes="config-label")
                yield Input(
                    placeholder="e.g., http://localhost:11434",
                    id="ollama-host-input"
                )
            
            # Status message
            yield Static("", id="status-message")
            
            # Buttons
            with Horizontal(id="button-container"):
                yield Button("Save", variant="primary", id="save", disabled=True)
    
    async def on_mount(self) -> None:
        """Pre-select saved configuration if available."""
        if self.saved_provider:
            # Use call_after_refresh to ensure widgets are ready
            self.call_after_refresh(self._restore_saved_configuration)
    
    def _restore_saved_configuration(self) -> None:
        """Restore saved configuration after widgets are ready."""
        # Find and select the saved provider
        provider_select = self.query_one("#provider-select", Select)
        
        # Set the value to the saved provider
        provider_select.value = self.saved_provider
        
        # Find the provider object
        self.selected_provider = next(p for p in PROVIDERS if p.name == self.saved_provider)
        
        # Show API key section if needed
        if self.selected_provider.requires_api_key:
            api_key_section = self.query_one("#api-key-section")
            api_key_section.remove_class("hidden")
            
            # Update label
            api_key_label = self.query_one("#api-key-label", Label)
            api_key_label.update(f"API Key ({self.selected_provider.setup_url}):")
            
            # Check if we have a saved API key
            from vibenix.secure_keys import get_api_key
            saved_api_key = get_api_key(self.selected_provider.env_var)
            if saved_api_key:
                # Update the placeholder to show key is configured
                api_key_input = self.query_one("#api-key-input", Input)
                api_key_input.placeholder = "API key already configured (leave blank to keep)"
        
        # Show Ollama host section if needed
        if self.selected_provider.name == "ollama":
            ollama_section = self.query_one("#ollama-section")
            ollama_section.remove_class("hidden")
            # Pre-populate saved Ollama host
            if self.saved_ollama_host:
                ollama_input = self.query_one("#ollama-host-input", Input)
                ollama_input.value = self.saved_ollama_host
        
        # Show model section
        model_section = self.query_one("#model-section")
        model_section.remove_class("hidden")
        
        # Load models asynchronously
        import asyncio
        asyncio.create_task(self._load_and_select_model())
        
        # Update button states
        self.update_button_states()
    
    async def _load_and_select_model(self) -> None:
        """Load models and pre-select saved model."""
        await self.load_models()
        
        # Pre-select the saved model if it's in the list
        if self.saved_model:
            # The model will be selected after models are loaded
            # Just set the selected model for now
            self.selected_model = self.saved_model
    
    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selection changes."""
        if event.select.id == "provider-select":
            # Find the selected provider
            self.selected_provider = next(
                p for p in PROVIDERS if p.name == event.value
            )
            
            # Show/hide API key section
            api_key_section = self.query_one("#api-key-section")
            if self.selected_provider.requires_api_key:
                api_key_section.remove_class("hidden")
                    
                # Update label with provider info
                api_key_label = self.query_one("#api-key-label", Label)
                api_key_label.update(
                    f"API Key ({self.selected_provider.setup_url}):"
                )
                
                # Clear any existing input
                api_key_input = self.query_one("#api-key-input", Input)
                api_key_input.value = ""
            else:
                api_key_section.add_class("hidden")
            
            # Show/hide Ollama host section
            ollama_section = self.query_one("#ollama-section")
            if self.selected_provider.name == "ollama":
                ollama_section.remove_class("hidden")
                # If we have a saved Ollama host, pre-populate it
                if hasattr(self, 'saved_ollama_host') and self.saved_ollama_host:
                    ollama_input = self.query_one("#ollama-host-input", Input)
                    ollama_input.value = self.saved_ollama_host
            else:
                ollama_section.add_class("hidden")
            
            # Show model section and populate models
            model_section = self.query_one("#model-section")
            model_section.remove_class("hidden")
            
            await self.load_models()
            
    
    async def load_models(self):
        """Load available models for the selected provider."""
        model_list = self.query_one("#model-list", ListView)
        status = self.query_one("#status-message", Static)
        
        # For providers that need API keys, check if we have one first
        if self.selected_provider.requires_api_key:
            api_key_input = self.query_one("#api-key-input", Input)
            api_key = api_key_input.value or os.environ.get(self.selected_provider.env_var)
            
            # If not in input or environment, check secure storage
            if not api_key:
                from vibenix.secure_keys import get_api_key
                api_key = get_api_key(self.selected_provider.env_var)
            
            if not api_key:
                status.update("Enter API key above to load models")
                model_list.clear()
                return
            
            # Temporarily set the API key for model discovery
            old_key = os.environ.get(self.selected_provider.env_var)
            os.environ[self.selected_provider.env_var] = api_key
        
        # For Ollama, ensure OLLAMA_API_BASE is set if we have a host
        if self.selected_provider.name == "ollama":
            ollama_input = self.query_one("#ollama-host-input", Input)
            if ollama_input.value.strip():
                os.environ["OLLAMA_API_BASE"] = ollama_input.value.strip()
        
        try:
            # Show loading message
            status.update("Loading available models...")
            
            # Get available models
            available_models = get_available_models(self.selected_provider)
            
            if available_models:
                model_list.clear()
                selected_index = None
                for i, model in enumerate(available_models):
                    model_list.append(ListItem(Label(model)))
                    # Check if this is the saved model
                    if hasattr(self, 'saved_model') and self.saved_model == model:
                        selected_index = i
                
                # Highlight the saved model if found
                if selected_index is not None:
                    model_list.index = selected_index
                    
                status.update("")
            else:
                status.update(f"No models found for {self.selected_provider.display_name}")
                model_list.clear()
        
        except Exception as e:
            logger.error(f"Error loading models for {self.selected_provider.name}: {e}")
            status.update(f"❌ Error: {str(e)}")
            model_list.clear()
        
        finally:
            # Restore original API key if we changed it
            if self.selected_provider.requires_api_key:
                if old_key is not None:
                    os.environ[self.selected_provider.env_var] = old_key
                elif self.selected_provider.env_var in os.environ:
                    del os.environ[self.selected_provider.env_var]
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle model selection from ListView."""
        if event.list_view.id == "model-list":
            # Get the selected model name from the label
            label = event.item.query_one(Label)
            self.selected_model = label.renderable
            
            self.update_button_states()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        if event.input.id == "custom-model-input" and event.value:
            self.selected_model = event.value
            # Clear model list selection
            model_list = self.query_one("#model-list", ListView)
            model_list.index = None
        elif event.input.id == "api-key-input" and event.value and self.selected_provider:
            # Reload models when API key is entered
            asyncio.create_task(self.load_models())
        elif event.input.id == "ollama-host-input" and self.selected_provider and self.selected_provider.name == "ollama":
            # Set the environment variable and reload models when Ollama host changes
            if event.value.strip():
                os.environ["OLLAMA_API_BASE"] = event.value.strip()
            else:
                # Remove the environment variable if empty
                os.environ.pop("OLLAMA_API_BASE", None)
            # Reload models with new host
            asyncio.create_task(self.load_models())
        
        self.update_button_states()
    
    def update_button_states(self):
        """Update button states based on current selections."""
        save_button = self.query_one("#save", Button)
        
        # Enable save button if we have all required info
        has_provider = self.selected_provider is not None
        has_model = bool(self.selected_model)
        
        has_api_key = True
        if self.selected_provider and self.selected_provider.requires_api_key:
            api_key_input = self.query_one("#api-key-input", Input)
            # Check if we have a key in the input OR in secure storage
            from vibenix.secure_keys import get_api_key
            saved_key = get_api_key(self.selected_provider.env_var)
            has_api_key = bool(api_key_input.value) or bool(saved_key)
        
        can_proceed = has_provider and has_model and has_api_key
        
        save_button.disabled = not can_proceed
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save":
            await self.save_configuration()
    
    
    async def save_configuration(self):
        """Save the configuration and dismiss."""
        # Set environment variables
        os.environ["MAGENTIC_BACKEND"] = "litellm"
        os.environ["MAGENTIC_LITELLM_MODEL"] = self.selected_model
        
        # Set and save API key if needed
        if self.selected_provider.requires_api_key:
            api_key_input = self.query_one("#api-key-input", Input)
            if api_key_input.value:
                # Save to secure storage
                from vibenix.secure_keys import set_api_key
                set_api_key(self.selected_provider.env_var, api_key_input.value)
                
                # Set in environment for current session
                os.environ[self.selected_provider.env_var] = api_key_input.value
        
        # Get Ollama host if provider is Ollama
        ollama_host = None
        if self.selected_provider.name == "ollama":
            ollama_input = self.query_one("#ollama-host-input", Input)
            ollama_host = ollama_input.value.strip() if ollama_input.value else None
        
        # Save to config file
        save_configuration(self.selected_provider, self.selected_model, ollama_host)
        
        # Dismiss with success
        self.dismiss({
            "provider": self.selected_provider.name,
            "model": self.selected_model,
            "ollama_host": ollama_host
        })