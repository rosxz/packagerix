"""All user prompts for packagerix.

This module contains all functions decorated with @ask_user that interact with the user.
"""

import re
from packagerix.ui.conversation import ask_user, coordinator_error


@ask_user("""@user Welcome to Packagerix! 🚀

I'm your friendly Nix packaging assistant. I can help you:
• Package projects from GitHub
• Build derivations with mkDerivation
• Identify and resolve dependencies
• Iteratively fix build errors

To get started, please provide the GitHub URL of the project you'd like to package.
You can optionally specify a git commit hash after the URL (e.g., https://github.com/owner/repo abc123def).

💡 Tip: Press Ctrl+L to toggle the log window and see application output.""")
def get_project_url(user_input: str) -> tuple[str, str | None]:
    """Get and validate the project URL from user. Returns (url, git_hash)."""
    parts = user_input.strip().split()
    
    if not parts or not parts[0].startswith("https://github.com/"):
        coordinator_error("URL must start with https://github.com/")
        return get_project_url()  # Ask again
    
    url = parts[0]
    git_hash = parts[1] if len(parts) > 1 else None
    
    if git_hash and not re.match(r'^[a-fA-F0-9]+$', git_hash):
        coordinator_error("Invalid git hash format. Please provide a valid commit hash.")
        return get_project_url()  # Ask again
    
    return url, git_hash


def evaluate_build_progress(prev_error: str, new_error: str) -> str:
    """Get user evaluation of build progress."""
    from packagerix.ui.conversation import get_ui_adapter
    
    # Create the formatted prompt with actual error content
    prompt = f"""@user Please evaluate the build progress by comparing the errors:

Previous error:
{prev_error}

New error:
{new_error}

Please choose:
1. error not resolved - build fails earlier (REGRESS)
2. code failed to evaluate (EVAL_ERROR) 
3. error resolved - build fails later (PROGRESS)
4. hash mismatch - needs correct hash to be filled in (HASH_MISMATCH)

Enter your choice (1-4):"""
    
    # Get the UI adapter and ask for input
    adapter = get_ui_adapter()
    response = adapter.ask_user(prompt)
    
    # Validate the response
    try:
        choice = int(response.strip())
        if 1 <= choice <= 4:
            return str(choice)
        else:
            coordinator_error("Please enter a number between 1 and 4")
            return evaluate_build_progress(prev_error, new_error)  # Ask again
    except ValueError:
        coordinator_error("Please enter a valid number")
        return evaluate_build_progress(prev_error, new_error)  # Ask again