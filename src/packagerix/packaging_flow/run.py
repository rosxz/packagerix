"""Business logic for packagerix using the coordinator pattern."""

from packagerix.ui.conversation import ask_user,  coordinator_message, coordinator_error, coordinator_progress
from packagerix.parsing import scrape_and_process, extract_updated_code, fetch_combined_project_data
from packagerix.flake import init_flake
from packagerix.nix import test_updated_code
from packagerix.packaging_flow.model_prompts import set_up_project, summarize_github, fix_build_error, fix_hash_mismatch
from packagerix.packaging_flow.user_prompts import get_project_url
from packagerix import config
from packagerix.errors import NixErrorKind



def analyze_project(project_page: str, release_data: dict = None) -> str:
    """Analyze the project using the model."""
    # summarize_github already has the @ask_model decorator
    return summarize_github(project_page, release_data)


def create_initial_package(template: str, project_page: str, release_data: dict = None) -> str:
    """Create initial package configuration."""
    # set_up_project now has the @ask_model decorator that handles UI and streaming
    result = set_up_project(template, project_page, release_data)
    return extract_updated_code(result)




def package_project(output_dir=None, project_url=None):
    """Main coordinator function for packaging a project."""
    # Step 1: Get project URL (includes welcome message)
    if project_url is None:
        project_url = get_project_url()
    else:
        # When URL is provided via CLI, still show welcome but skip prompt
        coordinator_message("Welcome to packagerix!")
    
    coordinator_progress(f"Fetching project information from {project_url}")
    
    # Step 2: Scrape project page
    try:
        project_page = scrape_and_process(project_url)
    except Exception as e:
        coordinator_error(f"Failed to fetch project page: {e}")
        return
    
    # Step 2b: Fetch release data from GitHub API
    release_data = None
    try:
        from packagerix.parsing import fetch_github_release_data
        release_data = fetch_github_release_data(project_url)
        if release_data:
            coordinator_message("Found GitHub release information via API")
    except Exception as e:
        coordinator_message(f"Could not fetch release data: {e}")
    
    # Step 3: Analyze project
    coordinator_message("I found the project information. Let me analyze it.")
    summary = analyze_project(project_page, release_data)
    
    # Step 4: Initialize flake
    coordinator_progress("Setting up a temporary Nix flake for packaging")
    flake = init_flake()
    coordinator_message(f"Working on temporary flake at {config.flake_dir}")
    
    # Step 5: Load template
    template_path = config.template_dir / "package.nix"
    starting_template = template_path.read_text()
    
    # Step 6: Create initial package
    coordinator_message("Creating initial package configuration...")
    code = create_initial_package(starting_template, project_page, release_data)
    
    # Step 7: Iterative build and fix loop
    max_attempts = 5
    is_initial_build = True
    
    for attempt in range(max_attempts):
        # Test build
        if attempt == 0:
            coordinator_progress("Testing the initial build...")
        else:
            coordinator_progress(f"Testing build attempt {attempt + 1}...")
            
        error = test_updated_code(code, is_initial_build=is_initial_build)
        is_initial_build = False
        
        # Check if build succeeded
        if error is None:
            if attempt == 0:
                coordinator_message("✅ Build succeeded on first try!")
            else:
                coordinator_message(f"✅ Build succeeded after {attempt} fixes!")
            if output_dir:
                save_package_output(code, project_url, output_dir)
            return code
        
        # Build failed, show error
        coordinator_message(f"Build attempt {attempt + 1}/{max_attempts} failed with error:")
        coordinator_message(f"```\n{error.error_message}\n```")
        
        # Fix the error based on type
        if error.type == NixErrorKind.HASH_MISMATCH:
            coordinator_message("Hash mismatch detected, fixing...")
            fixed_response = fix_hash_mismatch(code, error.error_message)
        else:
            # Regular error fixing
            fixed_response = fix_build_error(code, error.error_message)
        
        code = extract_updated_code(fixed_response)
    
    coordinator_error(f"Failed to build after {max_attempts} attempts. Manual intervention may be needed.")
    return None


def save_package_output(code: str, project_url: str, output_dir: str):
    """Save the package.nix file to the output directory."""
    import os
    import re
    from pathlib import Path
    
    # Extract package name from the code
    pname_match = re.search(r'pname\s*=\s*"([^"]+)"', code)
    if not pname_match:
        coordinator_error("Could not extract package name from code")
        return
    
    package_name = pname_match.group(1)
    
    # Create output directory structure
    output_path = Path(output_dir) / package_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save package.nix
    package_file = output_path / "package.nix"
    package_file.write_text(code)
    
    coordinator_message(f"Saved package to: {package_file}")


def run_packaging_flow(output_dir=None, project_url=None):
    """Run the complete packaging flow."""
    try:
        result = package_project(output_dir=output_dir, project_url=project_url)
        if result:
            coordinator_message("Packaging completed successfully!")
            coordinator_message(f"Final package code:\n```nix\n{result}\n```")
        else:
            coordinator_message("Packaging failed. Please check the errors above.")
    except Exception as e:
        coordinator_error(f"Unexpected error: {e}")
        raise