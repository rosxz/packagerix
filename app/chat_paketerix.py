from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Input, Static, Header, Footer, Button, RichLog
from textual.message import Message
from textual import on, work
from textual.worker import Worker, WorkerState
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
from app.nix import Error, get_last_ten_lines, invoke_build, test_updated_code, error_stack
from app.logging_config import logger, log_capture
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


class ProgressPoll(Static):
    """A widget for choosing build progress evaluation."""

    class ProgressChoice(Message):
        """Message sent when user makes a progress choice."""

        def __init__(self, choice: int):
            self.choice = choice
            super().__init__()

    def __init__(self, prev_error: str, new_error: str):
        self.prev_error = prev_error
        self.new_error = new_error
        super().__init__()

    def compose(self) -> ComposeResult:
        """Create the progress poll layout."""
        content = Text()
        content.append("🔍 Build Progress Evaluation\n\n", style="bold blue")
        content.append("Previous error:\n", style="bold")
        content.append(f"{self.prev_error}\n\n", style="red")
        content.append("New error:\n", style="bold")
        content.append(f"{self.new_error}\n\n", style="red")
        content.append("Did we make progress?", style="bold")

        yield Static(Panel(content, border_style="yellow", padding=(1, 2)))

        with Horizontal(id="progress-buttons"):
            regress_btn = Button("❌ Regress", id="choice-1", variant="error")
            regress_btn.tooltip = "Build fails earlier"
            yield regress_btn

            eval_btn = Button("⚠️ Eval Error", id="choice-2", variant="warning")
            eval_btn.tooltip = "Code failed to evaluate"
            yield eval_btn

            progress_btn = Button("✅ Progress", id="choice-3", variant="success")
            progress_btn.tooltip = "Build fails later"
            yield progress_btn

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle progress choice button press."""
        if event.button.id == "choice-1":
            choice = 1
        elif event.button.id == "choice-2":
            choice = 2
        elif event.button.id == "choice-3":
            choice = 3
        else:
            return

        self.post_message(self.ProgressChoice(choice))


class ChatHistory(ScrollableContainer):
    """Container for chat messages with auto-scroll."""

    def add_message(self, content: str, sender: str):
        """Add a new message to the chat."""
        message = ChatMessage(content, sender)
        self.mount(message)
        # Auto-scroll to bottom
        self.scroll_end(animate=False)

    def add_progress_poll(self, prev_error: str, new_error: str):
        """Add a progress evaluation poll to the chat."""
        poll = ProgressPoll(prev_error, new_error)
        self.mount(poll)
        self.scroll_end(animate=False)
        return poll


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
            self.clear()
            event.stop()
            event.prevent_default()


class LogWindow(Vertical):
    """A full-screen log window that displays captured logs."""
    
    def __init__(self):
        super().__init__()
        self.last_update_index = 0
        
    def compose(self) -> ComposeResult:
        """Create the log window layout."""
        yield Header()
        yield RichLog(highlight=True, markup=True, id="log-content")
        yield Footer()
        
    def update_logs(self):
        """Update the log widget with new log entries."""
        log_widget = self.query_one("#log-content", RichLog)
        logs = log_capture.get_logs()
        
        # If we're behind, clear and show all logs
        if self.last_update_index == 0 and logs:
            log_widget.clear()
            for log in logs:
                log_widget.write(log)
            self.last_update_index = len(logs)
        else:
            # Only add new logs since last update
            for log in logs[self.last_update_index:]:
                log_widget.write(log)
            self.last_update_index = len(logs)
        
    def clear_logs(self):
        """Clear all logs."""
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.clear()
        log_capture.clear()
        self.last_update_index = 0


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
        height: 4;
        margin: 0 1 2 1;
    }

    ChatInput {
        height: 3;
        margin: 1 0;
        border: none;
    }

    ChatHistory {
        height: 1fr;
        padding: 1;
    }

    ChatMessage {
        margin-bottom: 1;
    }

    ProgressPoll {
        margin-bottom: 1;
    }

    #progress-buttons {
        width: 100%;
        height: 3;
        align: center middle;
    }

    ProgressPoll Button {
        margin: 0 1;
        min-width: 20;
        height: 3;
        content-align: center middle;
        text-align: center;
        border: solid $accent;
        padding: 0 1;
        width: 1fr;
    }
    
    LogWindow {
        layer: logs;
        display: none;
    }
    
    LogWindow.-show-logs {
        display: block;
    }
    """
    
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+d", "quit", "Quit"),
        ("ctrl+l", "toggle_logs", "Toggle Logs"),
    ]
    
    def __init__(self):
        super().__init__()
        self.current_project_url = None
        self.current_flake_dir = None
        self.packaging_state = "idle"  # idle, analyzing, building, complete
        self.log_window = None
        self.log_update_timer = None
        
    def compose(self) -> ComposeResult:
        """Create the chat interface layout."""
        yield Header(show_clock=True)
        
        with Vertical(id="chat-container"):
            yield ChatHistory(id="chat-history")
        
        with Vertical(id="input-container"):
            yield Static("Type your message and press Enter:")
            yield ChatInput(placeholder="Ask paketerix about packaging your project...", id="chat-input")
        
        self.log_window = LogWindow()
        yield self.log_window
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the chat with a welcome message."""
        # Initialize paketerix config
        config.init()
        
        # Log startup
        logger.info("Paketerix Chat UI started")
        
        chat_history = self.query_one("#chat-history", ChatHistory)
        welcome_msg = (
            "Welcome to Paketerix! 🚀\n\n"
            "I'm your friendly Nix packaging assistant. I can help you:\n"
            "• Package projects from GitHub\n"
            "• Build derivations with mkDerivation\n"
            "• Identify and resolve dependencies\n"
            "• Iteratively fix build errors\n\n"
            "To get started, please provide the GitHub URL of the project you'd like to package.\n\n"
            "💡 Tip: Press Ctrl+L to toggle the log window and see application output."
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

        # Process the message in a worker thread
        self.process_user_input(event.content)

    @on(ProgressPoll.ProgressChoice)
    def handle_progress_choice(self, event: ProgressPoll.ProgressChoice) -> None:
        """Handle progress evaluation choice."""
        chat_history = self.query_one("#chat-history", ChatHistory)

        choices = {
            1: "❌ Regress (build fails earlier)",
            2: "⚠️ Eval Error (code failed to evaluate)",
            3: "✅ Progress (build fails later)"
        }

        choice_text = choices.get(event.choice, "Unknown choice")
        chat_history.add_message(f"Selected: {choice_text}", "user")

        # Continue with the build process based on choice
        asyncio.create_task(self.continue_build_process(event.choice))
    
    @work(exclusive=False, thread=True)
    def process_user_input(self, user_input: str) -> None:
        """Process user input and generate AI response in a worker thread."""
        chat_history = self.query_one("#chat-history", ChatHistory)
        
        # Add typing indicator
        typing_msg = ChatMessage("Paketerix is thinking... 🤔", "paketerix")
        self.call_from_thread(chat_history.mount, typing_msg)
        self.call_from_thread(chat_history.scroll_end, animate=False)
        
        try:
            # Process based on current state and input
            if "github.com" in user_input.lower() and user_input.startswith("https://github.com/"):
                self.handle_github_url_sync(user_input, chat_history)
            elif self.packaging_state == "analyzing" and any(word in user_input.lower() for word in ["yes", "y", "continue", "proceed"]):
                self.start_packaging_process_sync(chat_history)
            elif any(word in user_input.lower() for word in ["help", "what", "how"]):
                self.show_help_sync(chat_history)
            else:
                self.handle_general_input_sync(user_input, chat_history)
        except Exception as e:
            # Remove typing indicator and show error
            self.call_from_thread(typing_msg.remove)
            self.call_from_thread(chat_history.add_message, f"Sorry, I encountered an error: {str(e)}", "paketerix")
            return
        
        # Remove typing indicator
        self.call_from_thread(typing_msg.remove)
    
    def handle_github_url_sync(self, url: str, chat_history: ChatHistory) -> None:
        """Handle GitHub URL input and start analysis (synchronous version for worker thread)."""
        logger.info(f"Starting analysis of GitHub URL: {url}")
        logger.info(f"Worker thread - OLLAMA_HOST: {os.environ.get('OLLAMA_HOST', 'NOT SET')}")
        logger.info(f"Worker thread - MAGENTIC_LITELLM_MODEL: {os.environ.get('MAGENTIC_LITELLM_MODEL', 'NOT SET')}")
        
        self.current_project_url = url
        self.packaging_state = "analyzing"
        
        self.call_from_thread(chat_history.add_message, f"🔍 Analyzing repository: {url}", "paketerix")
        
        try:
            # Scrape and analyze the project - this is blocking
            logger.info("Scraping project page...")
            project_page = scrape_and_process(url)
            logger.info("Summarizing GitHub project...")
            from app.paketerix import summarize_github
            summary = summarize_github(project_page)
            
            response = (
                f"📋 **Project Analysis Complete!**\n\n"
                f"{summary}\n\n"
                f"I've analyzed the repository and gathered information about its build system "
                f"and dependencies. Would you like me to proceed with creating a Nix package? "
                f"(Type 'yes' to continue)"
            )
            self.call_from_thread(chat_history.add_message, response, "paketerix")
            
        except Exception as e:
            self.call_from_thread(chat_history.add_message, f"❌ Error analyzing repository: {str(e)}", "paketerix")
            self.packaging_state = "idle"
    
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
    
    def start_packaging_process_sync(self, chat_history: ChatHistory) -> None:
        """Start the actual packaging process (synchronous version for worker thread)."""
        self.packaging_state = "building"

        self.call_from_thread(chat_history.add_message, "🔨 Starting packaging process...", "paketerix")

        try:
            # Initialize flake
            flake = init_flake()
            self.current_flake_dir = config.flake_dir
            self.call_from_thread(chat_history.add_message, f"📁 Created temporary flake at: {self.current_flake_dir}", "paketerix")

            # Get project page data
            project_page = scrape_and_process(self.current_project_url)
            self.call_from_thread(chat_history.add_message, "📄 Project page information extracted", "paketerix")

            # Read template
            starting_template = (config.template_dir / "package.nix").read_text()

            # Show template info
            from app.nix import invoke_build, get_last_ten_lines, error_stack
            starting_template_error = invoke_build()
            error_stack.append(starting_template_error)
            starting_template_error_msg = get_last_ten_lines(starting_template_error.stderr)
            self.call_from_thread(chat_history.add_message, f"📋 Template status:\n```\n{starting_template_error_msg}\n```", "paketerix")

            # Generate initial package
            self.call_from_thread(chat_history.add_message, "🤖 Generating initial Nix derivation...", "paketerix")
            from app.paketerix import set_up_project
            model_reply = set_up_project(starting_template, project_page)
            self.call_from_thread(chat_history.add_message, f"📝 Model reply:\n```nix\n{model_reply}\n```", "paketerix")

            code = extract_updated_code(model_reply)
            self.call_from_thread(chat_history.add_message, "✅ Initial derivation created! Testing build...", "paketerix")

            # Test the build
            error = self.test_build_for_chat_sync(code)

            if error is None:
                self.call_from_thread(chat_history.add_message, "🎉 Build successful! Package is ready.", "paketerix")
                self.packaging_state = "complete"
            else:
                # Show the build process and ask for progress evaluation
                self.handle_build_error_sync(error, chat_history)

        except Exception as e:
            self.call_from_thread(chat_history.add_message, f"❌ Error during packaging: {str(e)}", "paketerix")
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
            chat_history.add_message("📄 Project page information extracted", "paketerix")

            # Read template
            starting_template = (config.template_dir / "package.nix").read_text()

            # Show template info
            from app.nix import invoke_build, get_last_ten_lines, error_stack
            starting_template_error = invoke_build()
            error_stack.append(starting_template_error)
            starting_template_error_msg = get_last_ten_lines(starting_template_error.stderr)
            chat_history.add_message(f"📋 Template status:\n```\n{starting_template_error_msg}\n```", "paketerix")

            # Generate initial package
            chat_history.add_message("🤖 Generating initial Nix derivation...", "paketerix")
            model_reply = set_up_project(starting_template, project_page)
            chat_history.add_message(f"📝 Model reply:\n```nix\n{model_reply}\n```", "paketerix")

            code = extract_updated_code(model_reply)
            chat_history.add_message("✅ Initial derivation created! Testing build...", "paketerix")

            # Test the build - use custom version for chat
            error = await self.test_build_for_chat(code)

            if error is None:
                chat_history.add_message("🎉 Build successful! Package is ready.", "paketerix")
                self.packaging_state = "complete"
            else:
                # Show the build process and ask for progress evaluation
                await self.handle_build_error(error, chat_history)

        except Exception as e:
            chat_history.add_message(f"❌ Error during packaging: {str(e)}", "paketerix")
            self.packaging_state = "idle"

    def test_build_for_chat_sync(self, updated_code: str):
        """Test build without triggering interactive eval_progress (synchronous version)."""
        from app.flake import update_flake

        # Update the flake with new code
        update_flake(updated_code)

        # Run the build
        result = invoke_build()
        error_stack.append(result)

        # Check if build succeeded
        if result.returncode == 0:
            return None
        else:
            # Return error info that will trigger our chat-based progress evaluation
            error_message = get_last_ten_lines(result.stderr)
            return Error(type=Error.ErrorType.EVAL_ERROR, error_message=error_message)
    
    def handle_build_error_sync(self, error, chat_history: ChatHistory) -> None:
        """Handle a build error by showing progress evaluation poll (synchronous version)."""
        from app.nix import error_stack, get_last_ten_lines

        # Get the error messages for comparison
        current_error_msg = get_last_ten_lines(error_stack[-1].stderr)
        prev_error_msg = get_last_ten_lines(error_stack[-2].stderr) if len(error_stack) > 1 else "No previous error"

        self.call_from_thread(chat_history.add_message,
            f"⚠️ Build failed with error:\n```\n{current_error_msg}\n```",
            "paketerix"
        )

        # Add the progress evaluation poll
        self.call_from_thread(chat_history.add_progress_poll, prev_error_msg, current_error_msg)
    
    async def handle_build_error(self, error, chat_history: ChatHistory) -> None:
        """Handle a build error by showing progress evaluation poll."""
        from app.nix import error_stack, get_last_ten_lines

        # Get the error messages for comparison
        current_error_msg = get_last_ten_lines(error_stack[-1].stderr)
        prev_error_msg = get_last_ten_lines(error_stack[-2].stderr) if len(error_stack) > 1 else "No previous error"

        chat_history.add_message(
            f"⚠️ Build failed with error:\n```\n{current_error_msg}\n```",
            "paketerix"
        )

        # Add the progress evaluation poll
        chat_history.add_progress_poll(prev_error_msg, current_error_msg)

    async def continue_build_process(self, choice: int) -> None:
        """Continue the build process based on user's progress choice."""
        chat_history = self.query_one("#chat-history", ChatHistory)

        if choice == 1:  # Regress
            chat_history.add_message("🔄 Build regressed. Attempting to fix in current context...", "paketerix")
        elif choice == 2:  # Eval Error
            chat_history.add_message("⚠️ Evaluation error detected. Fixing code issues...", "paketerix")
        elif choice == 3:  # Progress
            chat_history.add_message("✅ Progress made! Moving to next iteration...", "paketerix")

        # For now, show completion - later this would trigger actual iterative building
        await asyncio.sleep(1)
        chat_history.add_message("🔄 Continuing iterative build process...", "paketerix")
        self.packaging_state = "complete"

    async def test_build_for_chat(self, updated_code: str):
        """Test build without triggering interactive eval_progress."""
        from app.flake import update_flake

        # Update the flake with new code
        update_flake(updated_code)

        # Run the build
        result = invoke_build()
        error_stack.append(result)

        # Check if build succeeded
        if result.returncode == 0:
            return None
        else:
            # Return error info that will trigger our chat-based progress evaluation
            error_message = get_last_ten_lines(result.stderr)
            return Error(type=Error.ErrorType.EVAL_ERROR, error_message=error_message)
    
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
    
    def show_help_sync(self, chat_history: ChatHistory) -> None:
        """Show help information (synchronous version)."""
        help_text = (
            "ℹ️  **Paketerix Help**\n\n"
            "**Commands:**\n"
            "• Paste a GitHub URL to start packaging\n"
            "• Type 'help' for this help message\n"
            "• Press Ctrl+L to toggle the log window\n"
            "• Use Ctrl+C or Ctrl+D to quit\n\n"
            "**Packaging Process:**\n"
            "1. 🔍 Repository analysis - I examine the project structure\n"
            "2. 📋 Dependency identification - I find build requirements\n"
            "3. 🔨 Initial derivation - I create a basic Nix package\n"
            "4. 🔄 Iterative fixes - I resolve build errors automatically\n"
            "5. ✅ Final package - Ready-to-use Nix derivation\n\n"
            "**Current State:** " + self.packaging_state.title()
        )
        self.call_from_thread(chat_history.add_message, help_text, "paketerix")
    
    def handle_general_input_sync(self, user_input: str, chat_history: ChatHistory) -> None:
        """Handle general user input (synchronous version)."""
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
        
        self.call_from_thread(chat_history.add_message, response, "paketerix")
    
    async def show_help(self, chat_history: ChatHistory) -> None:
        """Show help information."""
        help_text = (
            "ℹ️  **Paketerix Help**\n\n"
            "**Commands:**\n"
            "• Paste a GitHub URL to start packaging\n"
            "• Type 'help' for this help message\n"
            "• Press Ctrl+L to toggle the log window\n"
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
    
    def action_toggle_logs(self) -> None:
        """Toggle the visibility of the log window."""
        logger.debug("Toggling log window")
        self.log_window.toggle_class("-show-logs")
        
        if self.log_window.has_class("-show-logs"):
            logger.debug("Showing log window")
            self.log_window.update_logs()
            # Start periodic log updates
            if not self.log_update_timer:
                self.log_update_timer = self.set_interval(0.5, self.update_logs)
        else:
            logger.debug("Hiding log window")
            # Stop log updates
            if self.log_update_timer:
                self.log_update_timer.stop()
                self.log_update_timer = None
    
    def update_logs(self) -> None:
        """Periodically update the log window with new logs."""
        if self.log_window and self.log_window.has_class("-show-logs"):
            self.log_window.update_logs()


def main():
    """Main entry point for the chat UI."""
    app = PaketerixChatApp()
    app.run()


if __name__ == "__main__":
    main()
