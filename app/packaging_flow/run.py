"""Business logic for paketerix using the coordinator pattern."""

from app.ui.conversation import ask_user,  coordinator_message, coordinator_error, coordinator_progress
from app.parsing import scrape_and_process, extract_updated_code
from app.flake import init_flake
from app.nix import test_updated_code
from app.packaging_flow.model_prompts import set_up_project, summarize_github, fix_build_error
from app.packaging_flow.user_prompts import get_project_url
from app import config



def analyze_project(project_page: str) -> str:
    """Analyze the project using the model."""
    # summarize_github already has the @ask_model decorator
    return summarize_github(project_page)


def create_initial_package(template: str, project_page: str) -> str:
    """Create initial package configuration."""
    # set_up_project now has the @ask_model decorator that handles UI and streaming
    result = set_up_project(template, project_page)
    return extract_updated_code(result)




def package_project():
    """Main coordinator function for packaging a project."""
    # Step 1: Get project URL (includes welcome message)
    project_url = get_project_url()
    
    coordinator_progress(f"Fetching project information from {project_url}")
    
    # Step 2: Scrape project page
    try:
        project_page = scrape_and_process(project_url)
    except Exception as e:
        coordinator_error(f"Failed to fetch project page: {e}")
        return
    
    # Step 3: Analyze project
    coordinator_message("I found the project information. Let me analyze it.")
    summary = analyze_project(project_page)
    
    # Step 4: Initialize flake
    coordinator_progress("Setting up a temporary Nix flake for packaging")
    flake = init_flake()
    coordinator_message(f"Working on temporary flake at {config.flake_dir}")
    
    # Step 5: Load template
    template_path = config.template_dir / "package.nix"
    starting_template = template_path.read_text()
    
    # Step 6: Create initial package
    coordinator_message("Creating initial package configuration...")
    code = create_initial_package(starting_template, project_page)
    
    # Step 7: Test build
    coordinator_progress("Testing the initial build...")
    error = test_updated_code(code)
    
    if error is None:
        coordinator_message("✅ Build succeeded on first try!")
        return code
    
    # Step 8: Iterative fixing
    max_attempts = 5
    for attempt in range(max_attempts):
        coordinator_message(f"Build attempt {attempt + 1}/{max_attempts} failed with error:")
        coordinator_message(f"```\n{error.error_message}\n```")
        
        # Fix the error
        fixed_response = fix_build_error(code, error)
        code = extract_updated_code(fixed_response)
        
        # Test again
        coordinator_progress(f"Testing build attempt {attempt + 2}...")
        error = test_updated_code(code)
        
        if error is None:
            coordinator_message(f"✅ Build succeeded after {attempt + 1} fixes!")
            return code
    
    coordinator_error(f"Failed to build after {max_attempts} attempts. Manual intervention may be needed.")
    return None


def run_packaging_flow():
    """Run the complete packaging flow."""
    try:
        result = package_project()
        if result:
            coordinator_message("Packaging completed successfully!")
            coordinator_message(f"Final package code:\n```nix\n{result}\n```")
        else:
            coordinator_message("Packaging failed. Please check the errors above.")
    except Exception as e:
        coordinator_error(f"Unexpected error: {e}")
        raise