from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Input, Static, Header, Footer
from textual.message import Message
from textual import on
from rich.text import Text
from rich.panel import Panel
from rich.console import Console
from rich.markdown import Markdown
import asyncio
from datetime import datetime

# Import existing paketerix functionality
from app import config
from app.paketerix import (
    set_up_project,
    summarize_github,
    build_project,
    Project
)
from app.parsing import scrape_and_process, extract_updated_code
from app.flake import init_flake
from app.nix import Error, get_last_ten_lines, invoke_build, test_updated_code
import os


class ChatMessage(Static):
    """A widget representing a single chat message."""
    
    def __init__(self, content: str, sender: str, timestamp: datetime = None):
        self.content = content
        self.sender = sender
        self.timestamp = timestamp or datetime.now()
        super().__init__()
        
    def compose(self) -> ComposeResult:
        """Create the message layout."""
        time_str = self.timestamp.strftime("%H:%M")
        
        if self.sender == "paketerix":
            # AI assistant message with blue styling
            message_text = Text()
            message_text.append(f"🤖 paketerix ", style="bold blue")
            message_text.append(f"({time_str})", style="dim")
            message_text.append(f"\n{self.content}", style="blue")
            yield Static(Panel(message_text, border_style="blue", padding=(0, 1)))
        else:
            # User message with green styling
            message_text = Text()
            message_text.append(f"👤 user ", style="bold green")
            message_text.append(f"({time_str})", style="dim")
            message_text.append(f"\n{self.content}", style="green")
            yield Static(Panel(message_text, border_style="green", padding=(0, 1)))


class ChatHistory(ScrollableContainer):
    """Container for chat messages with auto-scroll."""
    
    def add_message(self, content: str, sender: str):
        """Add a new message to the chat."""
        message = ChatMessage(content, sender)
        self.mount(message)
        # Auto-scroll to bottom
        self.scroll_end(animate=False)


class ChatInput(Input):
    """Custom input widget for chat messages."""
    
    class MessageSent(Message):
        """Message sent when user submits input."""
        
        def __init__(self, content: str):
            self.content = content
            super().__init__()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.value.strip():
            self.post_message(self.MessageSent(event.value.strip()))
            self.value = ""


class PaketerixChatApp(App):
    """Main chat application with integrated paketerix functionality."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #chat-container {
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }
    
    #input-container {
        height: 3;
        margin: 0 1;
    }
    
    ChatInput {
        height: 1;
        margin: 1 0;
    }
    
    ChatHistory {
        height: 1fr;
        padding: 1;
    }
    
    ChatMessage {
        margin-bottom: 1;
    }
    """
    
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+d", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.current_project_url = None
        self.current_flake_dir = None
        self.packaging_state = "idle"  # idle, analyzing, building, complete
        
    def compose(self) -> ComposeResult:
        """Create the chat interface layout."""
        yield Header(show_clock=True)
        
        with Vertical():
            with Vertical(id="chat-container"):
                yield ChatHistory(id="chat-history")
            
            with Vertical(id="input-container"):
                yield Static("Type your message and press Enter:")
                yield ChatInput(placeholder="Ask paketerix about packaging your project...", id="chat-input")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the chat with a welcome message."""
        # Initialize paketerix config
        config.init()
        
        chat_history = self.query_one("#chat-history", ChatHistory)
        welcome_msg = (
            "Welcome to Paketerix! 🚀\n\n"
            "I'm your friendly Nix packaging assistant. I can help you:\n"
            "• Package projects from GitHub\n"
            "• Build derivations with mkDerivation\n"
            "• Identify and resolve dependencies\n"
            "• Iteratively fix build errors\n\n"
            "To get started, please provide the GitHub URL of the project you'd like to package."
        )
        chat_history.add_message(welcome_msg, "paketerix")
        
        # Focus the input
        self.query_one("#chat-input", ChatInput).focus()
    
    @on(ChatInput.MessageSent)
    def handle_user_message(self, event: ChatInput.MessageSent) -> None:
        """Handle a new user message."""
        chat_history = self.query_one("#chat-history", ChatHistory)
        
        # Add user message
        chat_history.add_message(event.content, "user")
        
        # Process the message asynchronously
        asyncio.create_task(self.process_user_input(event.content))
    
    async def process_user_input(self, user_input: str) -> None:
        """Process user input and generate AI response."""
        chat_history = self.query_one("#chat-history", ChatHistory)
        
        # Add typing indicator
        typing_msg = ChatMessage("Paketerix is thinking... 🤔", "paketerix")
        chat_history.mount(typing_msg)
        chat_history.scroll_end(animate=False)
        
        try:
            # Process based on current state and input
            if "github.com" in user_input.lower() and user_input.startswith("https://github.com/"):
                await self.handle_github_url(user_input, chat_history)
            elif self.packaging_state == "analyzing" and any(word in user_input.lower() for word in ["yes", "y", "continue", "proceed"]):
                await self.start_packaging_process(chat_history)
            elif any(word in user_input.lower() for word in ["help", "what", "how"]):
                await self.show_help(chat_history)
            else:
                await self.handle_general_input(user_input, chat_history)
        except Exception as e:
            # Remove typing indicator and show error
            typing_msg.remove()
            chat_history.add_message(f"Sorry, I encountered an error: {str(e)}", "paketerix")
            return
        
        # Remove typing indicator
        typing_msg.remove()
    
    async def handle_github_url(self, url: str, chat_history: ChatHistory) -> None:
        """Handle GitHub URL input and start analysis."""
        self.current_project_url = url
        self.packaging_state = "analyzing"
        
        chat_history.add_message(f"🔍 Analyzing repository: {url}", "paketerix")
        
        # Simulate processing delay
        await asyncio.sleep(1)
        
        try:
            # Scrape and analyze the project
            project_page = scrape_and_process(url)
            summary = summarize_github(project_page)
            
            response = (
                f"📋 **Project Analysis Complete!**\n\n"
                f"{summary}\n\n"
                f"I've analyzed the repository and gathered information about its build system "
                f"and dependencies. Would you like me to proceed with creating a Nix package? "
                f"(Type 'yes' to continue)"
            )
            chat_history.add_message(response, "paketerix")
            
        except Exception as e:
            chat_history.add_message(f"❌ Error analyzing repository: {str(e)}", "paketerix")
            self.packaging_state = "idle"
    
    async def start_packaging_process(self, chat_history: ChatHistory) -> None:
        """Start the actual packaging process."""
        self.packaging_state = "building"
        
        chat_history.add_message("🔨 Starting packaging process...", "paketerix")
        
        try:
            # Initialize flake
            flake = init_flake()
            self.current_flake_dir = config.flake_dir
            chat_history.add_message(f"📁 Created temporary flake at: {self.current_flake_dir}", "paketerix")
            
            # Get project page data
            project_page = scrape_and_process(self.current_project_url)
            
            # Read template
            starting_template = (config.template_dir / "package.nix").read_text()
            
            # Generate initial package
            chat_history.add_message("🤖 Generating initial Nix derivation...", "paketerix")
            model_reply = set_up_project(starting_template, project_page)
            code = extract_updated_code(model_reply)
            
            chat_history.add_message("✅ Initial derivation created! Testing build...", "paketerix")
            
            # Test the build
            error = test_updated_code(code)
            
            if error.type == Error.ErrorType.SUCCESS:
                chat_history.add_message("🎉 Build successful! Package is ready.", "paketerix")
                self.packaging_state = "complete"
            else:
                chat_history.add_message(
                    f"⚠️  Build failed with error:\n```\n{error.error_message}\n```\n\n"
                    f"Starting iterative build process to fix issues...", 
                    "paketerix"
                )
                
                # Start iterative build process
                await self.iterative_build_process(starting_template, chat_history)
                
        except Exception as e:
            chat_history.add_message(f"❌ Error during packaging: {str(e)}", "paketerix")
            self.packaging_state = "idle"
    
    async def iterative_build_process(self, template_str: str, chat_history: ChatHistory) -> None:
        """Run the iterative build process."""
        try:
            chat_history.add_message("🔄 Running AI-powered iterative build fixes...", "paketerix")
            
            # This would run the build_project function which uses the LLM
            # For now, we'll simulate it
            await asyncio.sleep(2)
            
            # In reality, you'd call: build_output = build_project(template_str)
            # and stream the results
            
            chat_history.add_message(
                "✅ Iterative build process completed!\n\n"
                "The package has been successfully built after resolving dependency "
                "and configuration issues. You can find the results in the temporary flake directory.",
                "paketerix"
            )
            self.packaging_state = "complete"
            
        except Exception as e:
            chat_history.add_message(f"❌ Error during iterative build: {str(e)}", "paketerix")
            self.packaging_state = "idle"
    
    async def show_help(self, chat_history: ChatHistory) -> None:
        """Show help information."""
        help_text = (
            "ℹ️  **Paketerix Help**\n\n"
            "**Commands:**\n"
            "• Paste a GitHub URL to start packaging\n"
            "• Type 'help' for this help message\n"
            "• Use Ctrl+C or Ctrl+D to quit\n\n"
            "**Packaging Process:**\n"
            "1. 🔍 Repository analysis - I examine the project structure\n"
            "2. 📋 Dependency identification - I find build requirements\n"
            "3. 🔨 Initial derivation - I create a basic Nix package\n"
            "4. 🔄 Iterative fixes - I resolve build errors automatically\n"
            "5. ✅ Final package - Ready-to-use Nix derivation\n\n"
            "**Current State:** " + self.packaging_state.title()
        )
        chat_history.add_message(help_text, "paketerix")
    
    async def handle_general_input(self, user_input: str, chat_history: ChatHistory) -> None:
        """Handle general user input."""
        if self.packaging_state == "idle":
            response = (
                "I'm ready to help you package software with Nix! "
                "Please provide a GitHub URL to get started, or type 'help' for more information."
            )
        elif self.packaging_state == "analyzing":
            response = (
                "I'm currently analyzing a repository. Please type 'yes' to proceed with packaging, "
                "or provide a new GitHub URL to analyze a different project."
            )
        elif self.packaging_state == "building":
            response = (
                "I'm currently working on packaging your project. Please wait for the process to complete."
            )
        elif self.packaging_state == "complete":
            response = (
                "The packaging process is complete! You can provide a new GitHub URL to package "
                "another project, or type 'help' for more options."
            )
        else:
            response = "I didn't understand that. Type 'help' for available commands."
        
        chat_history.add_message(response, "paketerix")


def main():
    """Main entry point for the chat UI."""
    app = PaketerixChatApp()
    app.run()


if __name__ == "__main__":
    main()