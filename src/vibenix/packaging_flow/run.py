"""Business logic for vibenix using the coordinator pattern."""

import subprocess
from pathlib import Path
from pydantic import BaseModel

from vibenix.ui.conversation import ask_user,  coordinator_message, coordinator_error, coordinator_progress
from vibenix.parsing import scrape_and_process, extract_updated_code, fetch_combined_project_data, fill_src_attributes
from vibenix.flake import init_flake
from vibenix.nix import eval_progress, execute_build_and_add_to_stack
from vibenix.packaging_flow.model_prompts import (
    pick_template, summarize_github, set_up_project, fix_build_error, fix_hash_mismatch,
    evaluate_code, refine_code, get_feedback, RefinementExit, 
    analyze_package_failure, classify_packaging_failure, PackagingFailure
)
from vibenix.packaging_flow.user_prompts import get_project_url
from vibenix import config
from vibenix.errors import NixBuildErrorDiff, NixErrorKind, NixBuildResult
from vibenix.tools.file_tools import create_source_function_calls
from vibenix.ccl_log import init_logger, get_logger, close_logger
import os

class Solution(BaseModel):
    """Represents a solution candidate with its code and build result."""
    code: str
    result: NixBuildResult


def get_nixpkgs_source_path() -> str:
    """Get the nixpkgs source path from the template flake."""
    try:
        result = subprocess.run(
            ["nix", "build", ".#nixpkgs-src", "--no-link", "--print-out-paths"],
            cwd=config.template_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        coordinator_error(f"Failed to get nixpkgs source path: {e}")
        raise



def analyze_project(project_page: str) -> str:
    """Analyze the project using the model."""
    # summarize_github already has the @ask_model decorator
    return summarize_github(project_page)


def create_initial_package(template: str, project_page: str, template_notes: str = None) -> str:
    """Create initial package configuration."""
    # set_up_project now has the @ask_model decorator that handles UI and streaming
    result = set_up_project(template, project_page, template_notes)
    return extract_updated_code(result)


def run_nurl(url, rev=None):
    """Run nurl command and return the output."""
    try:
        cmd = ['nurl', url, rev] if rev else ['nurl', url]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.lower()
        # Check for various rate limit indicators
        if any(indicator in error_output for indicator in ["rate limit", "429", "403", "forbidden"]):
            print(f"Rate limit/forbidden error for {url}")
            return "RATE_LIMITED"
        print(f"Error running nurl for {url}: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Error: nurl command not found. Please ensure nurl is installed.")
        return None


def read_fetcher_file(fetcher: str) -> str:
    """Read the fetcher file content."""
    from pathlib import Path
    try:
        path = Path(fetcher)
        with open(path, 'r') as f:
            # Ignore comments and empty lines
            return "".join(line for line in f if line.strip() and not line.startswith("#"))
    except FileNotFoundError:
        coordinator_error(f"Fetcher file '{fetcher}' not found.")
        raise
    except Exception as e:
        coordinator_error(f"Error reading fetcher file: {e}")
        raise


def refine_package(curr: Solution, project_page: str):
    """Refinement cycle to improve the packaging."""
    max_iterations = 3

    for iteration in range(max_iterations):
        # Get feedback for current code
        # TODO BUILD LOG IS NOT BEING PASSED!
        feedback = get_feedback(curr.code, "", project_page)
        coordinator_message(f"Refining package (iteration {iteration}/{max_iterations})...")
        coordinator_message(f"Received feedback: {feedback}")

        # Pass the feedback to the generator (refine_code)
        response = refine_code(curr.code, feedback, project_page)
        updated_code = extract_updated_code(response)
        updated_res = execute_build_and_add_to_stack(updated_code)
        attempt = Solution(code=updated_code, result=updated_res)
        
        # Verify the updated code still builds
        if not attempt.result.success:
            coordinator_error(f"Refinement caused a regression ({attempt.result.error.type}), reverting to last successful solution.")
        else:
            coordinator_message("Refined packaging code successfuly builds, continuing...")
            curr = attempt
    coordinator_message("Refinement process reached its conclusion (max iterations).")
    return curr


def package_project(output_dir=None, project_url=None, revision=None, fetcher=None):
    """Main coordinator function for packaging a project."""
    # Initialize CCL logger
    log_file = Path(output_dir) / "run.ccl" if output_dir else Path("run.ccl")
    ccl_logger = init_logger(log_file)
    
    # Step 1: Get project URL (includes welcome message)
    if project_url is None:
        project_url = get_project_url()
    else:
        # When URL is provided via CLI, still show welcome but skip prompt
        coordinator_message("Welcome to vibenix!")
    
    # Log session start
    ccl_logger.log_session_start(project_url)
    
    # Log model configuration
    model = os.environ.get("MAGENTIC_LITELLM_MODEL", "unknown")
    ccl_logger.log_model_config(model)

    # Obtain the project fetcher
    if fetcher: 
        coordinator_progress(f"Using provided fetcher: {fetcher}")
        fetcher = read_fetcher_file(fetcher)
        if revision:
            coordinator_error("Ignoring revision parameter in favor of provided fetcher.")
    else:
        coordinator_progress("Obtaining project fetcher from the provided URL")
        fetcher = run_nurl(project_url, revision)

    coordinator_progress(f"Fetching project information from {project_url}")
    
    # Step 2: Scrape project page
    try:
        project_page = scrape_and_process(project_url)
    except Exception as e:
        coordinator_error(f"Failed to fetch project page: {e}")
        return
    
    # Step 2b: Release data fetching removed - no longer needed
    
    # Step 3: Analyze project
    coordinator_message("I found the project information. Let me analyze it.")
    summary = analyze_project(project_page)

    # Step 4: Initialize flake
    coordinator_progress("Setting up a temporary Nix flake for packaging")
    init_flake()
    coordinator_message(f"Working on temporary flake at {config.flake_dir}")
    
    # Step 5: Load template
    template_type = pick_template(summary)
    coordinator_message(f"Selected template: {template_type.value}")
    ccl_logger.log_template_selected(template_type.value)
    template_filename = f"{template_type.value}.nix"
    template_path = config.template_dir / template_filename
    starting_template = template_path.read_text()
    
    # Load optional notes file
    notes_filename = f"{template_type.value}.notes"
    notes_path = config.template_dir / notes_filename
    template_notes = notes_path.read_text() if notes_path.exists() else None

    # Step 6.a: Manual src setup
    coordinator_message("Setting up the src attribute in the template...")
    initial_code, store_path = fill_src_attributes(starting_template, fetcher)

    # Create functions for both the project source and nixpkgs
    project_functions = create_source_function_calls(store_path, "project_")
    nixpkgs_path = get_nixpkgs_source_path()
    nixpkgs_functions = create_source_function_calls(nixpkgs_path, "nixpkgs_")
    additional_functions = project_functions + nixpkgs_functions
    
    # Step 7: Agentic loop
    coordinator_progress("Testing the initial build...")
    initial_result = execute_build_and_add_to_stack(initial_code)
    best = Solution(code=initial_code, result=initial_result)

    # Log that we're starting iterations
    ccl_logger.log_before_iterations()
    
    iteration = 0
    MAX_ITERATIONS = 40
    candidate = best
    MAX_CONSECUTIVE_REBUILDS_WITHOUT_PROGRESS = 10
    consecutive_rebuilds_without_progress = 0
    # we have to evaluate if a small limit here helps or hurts
    # or just get rid of it
    MAX_CONSECUTIVE_NON_BUILD_ERRORS = 99
    consecutive_non_build_errors = 0

    first_build_error = True
    has_broken_log_output = False
    
    # Track attempted tool calls to avoid repetition
    attempted_tool_calls = []
    
    while (
        (not candidate.result.success) and
        (iteration < MAX_ITERATIONS) and
        (consecutive_rebuilds_without_progress < MAX_CONSECUTIVE_REBUILDS_WITHOUT_PROGRESS)):
      
        coordinator_message(f"Iteration {iteration + 1}:")
        coordinator_message(f"```\n{candidate.result.error.truncated()}\n```")
        ccl_logger.log_iteration_start(iteration)
        
        if candidate.result.error.type == NixErrorKind.HASH_MISMATCH:
            coordinator_message("Hash mismatch detected, fixing...")
            coordinator_message(f"code:\n{candidate.code}\n")
            coordinator_message(f"error:\n{candidate.result.error.truncated()}\n")
            fixed_response = fix_hash_mismatch(candidate.code, candidate.result.error.truncated())
        else:
            coordinator_message("Other error detected, fixing...")
            coordinator_message(f"code:\n{candidate.code}\n")
            coordinator_message(f"error:\n{candidate.result.error.truncated()}\n")
            
            # Create a collector for this iteration's tool calls
            iteration_tool_calls = []
            is_dependency_error = candidate.result.error.type == NixErrorKind.DEPENDENCY_BUILD_ERROR
            fixed_response = fix_build_error(
                candidate.code, 
                candidate.result.error.truncated(), 
                summary, 
                template_notes, 
                additional_functions, 
                has_broken_log_output,
                is_dependency_error,
                attempted_tool_calls,
                iteration_tool_calls
            )
            
            # Add this iteration's tool calls to the attempted list
            attempted_tool_calls.extend(iteration_tool_calls)
        
        updated_code = extract_updated_code(fixed_response)
            
        # Test the fix
        coordinator_progress(f"Iteration {iteration + 1}: Testing fix attempt {iteration + 1} of {MAX_ITERATIONS}...")
        new_result = execute_build_and_add_to_stack(updated_code)
        candidate = Solution(code=updated_code, result=new_result)

        if not new_result.success:
            if new_result.error.type == NixErrorKind.BUILD_ERROR:
                coordinator_message(f"Nix build result: {candidate.result.error.type}")
                if first_build_error:
                    eval_result = NixBuildErrorDiff.PROGRESS
                    first_build_error = False
                elif best.result.error == candidate.result.error:
                    eval_result = NixBuildErrorDiff.REGRESS
                else:
                    eval_result = eval_progress(best.result, candidate.result, iteration)
                    ccl_logger.log_progress_eval(iteration, eval_result)
                
                if eval_result == NixBuildErrorDiff.PROGRESS:
                    coordinator_message(f"Iteration {iteration + 1} made progress...")
                    best = candidate
                    consecutive_rebuilds_without_progress = 0
                    has_broken_log_output = False  # Reset since we made progress
                    attempted_tool_calls = []  # Reset tool calls since we made progress
                elif eval_result == NixBuildErrorDiff.BROKEN_LOG_OUTPUT:
                    coordinator_message(f"Iteration {iteration + 1} produced broken log output - continuing without rollback...")
                    has_broken_log_output = True
                    # Don't update best, but also don't rollback candidate
                    # Don't increment consecutive_rebuilds_without_progress since this is a special case
                elif eval_result == NixBuildErrorDiff.STAGNATION:
                    if has_broken_log_output:
                        # Stagnation after broken log output means we fixed the log output!
                        coordinator_message(f"Iteration {iteration + 1} fixed broken log output (now showing clear error)...")
                        best = candidate
                        has_broken_log_output = False
                        consecutive_rebuilds_without_progress = 0
                        attempted_tool_calls = []  # Reset tool calls since we fixed log output
                    else:
                        coordinator_message(f"Iteration {iteration + 1} stagnated...")
                        candidate = best
                        consecutive_rebuilds_without_progress += 1
                else:  # REGRESS
                    coordinator_message(f"Iteration {iteration + 1} regressed...")
                    candidate = best
                    consecutive_rebuilds_without_progress += 1
                consecutive_non_build_errors = 0
            else:
                # Non-build errors (EVAL_ERROR, HASH_MISMATCH, DEPENDENCY_BUILD_ERROR)
                coordinator_message(f"Non-build error: {new_result.error.type}")
                consecutive_non_build_errors += 1          
                if consecutive_non_build_errors >= MAX_CONSECUTIVE_NON_BUILD_ERRORS:
                    candidate = best
                    consecutive_non_build_errors = 0

        ccl_logger.log_iteration_end(iteration, new_result)
        
        # Log iteration cost and token usage
        from vibenix.packaging_flow.model_prompts import end_stream_logger
        # The iteration cost would be the difference from the start of this iteration
        # For now, we'll log the cumulative cost
        ccl_logger.log_iteration_cost(
            iteration=iteration,
            iteration_cost=end_stream_logger.total_cost,
            input_tokens=end_stream_logger.total_input_tokens,
            output_tokens=end_stream_logger.total_output_tokens
        )
        
        iteration += 1

    if candidate.result.success:
        coordinator_message("Build succeeded! Refining package...")
        candidate = refine_package(candidate, summary)
        
        # Always log success and return, regardless of refinement outcome
        from vibenix.packaging_flow.model_prompts import end_stream_logger
        ccl_logger.log_session_end(True, iteration, end_stream_logger.total_cost)
        close_logger()
        if output_dir:
            save_package_output(candidate.code, project_url, output_dir)
        return candidate.code  
    else:
        if consecutive_non_build_errors >= MAX_CONSECUTIVE_NON_BUILD_ERRORS:
            coordinator_error(f"Aborted: {consecutive_rebuilds_without_progress} consecutive rebuilds without progress.")

        else:
            coordinator_error(f"Reached MAX_ITERATIONS build iteration limit of {MAX_ITERATIONS}.")
    
    details = analyze_package_failure(best.code, best.result.error.truncated(), summary, template_notes, additional_functions)
    packaging_failure = classify_packaging_failure(details)
    if isinstance(packaging_failure, PackagingFailure):
        coordinator_message(f"Packaging failure type: {packaging_failure}\nDetails:\n{details}\n")
    from vibenix.packaging_flow.model_prompts import end_stream_logger
    ccl_logger.log_session_end(False, iteration, end_stream_logger.total_cost)
    close_logger()
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


def run_packaging_flow(output_dir=None, project_url=None, revision=None, fetcher=None):
    """Run the complete packaging flow."""
    try:
        result = package_project(output_dir=output_dir, project_url=project_url,
                                revision=revision, fetcher=fetcher)
        if result:
            coordinator_message("Packaging completed successfully!")
            coordinator_message(f"Final package code:\n```nix\n{result}\n```")
            # Print total API cost
            from vibenix.packaging_flow.model_prompts import end_stream_logger
            if end_stream_logger.total_cost > 0:
                coordinator_message(f"\n💰 Total API cost: ${end_stream_logger.total_cost:.6f}")
        else:
            coordinator_message("Packaging failed. Please check the errors above.")
            # Print total API cost even on failure
            from vibenix.packaging_flow.model_prompts import end_stream_logger
            if end_stream_logger.total_cost > 0:
                coordinator_message(f"\n💰 Total API cost: ${end_stream_logger.total_cost:.6f}")
    except Exception as e:
        coordinator_error(f"Unexpected error: {e}")
        raise
