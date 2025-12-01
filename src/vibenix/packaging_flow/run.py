"""Business logic for vibenix using the coordinator pattern."""

import re
import subprocess
from pathlib import Path
from typing import Optional

from vibenix.ui.conversation import coordinator_message, coordinator_error, coordinator_progress
from vibenix.parsing import fetch_github_release_data, scrape_and_process, fill_src_attributes, get_store_path
from vibenix.flake import init_flake, get_package_contents
from vibenix.nix import execute_build_and_add_to_stack, revert_packaging_to_solution
from vibenix.packaging_flow.model_prompts import (
    pick_template, summarize_github, summarize_project_source,
    analyze_package_failure, classify_packaging_failure, PackagingFailure,
    summarize_build, choose_builders, compare_template_builders, get_model_prompt_manager
)
from vibenix.packaging_flow.refinement import refine_package
from vibenix.packaging_flow.user_prompts import get_project_url
from vibenix import config
from vibenix.tools.file_tools import create_source_function_calls
from vibenix.ccl_log import init_logger, get_logger, close_logger, enum_str
from vibenix.git_info import get_git_info
from vibenix.tools.view import _view as view_package_contents
from vibenix.defaults.vibenix_settings import get_settings_manager


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



def analyze_project(project_page: Optional[str]=None,
                    source_info: Optional[tuple[str, str]]=None) -> str:
    """Analyze the project using the model."""
    if project_page:
        return summarize_github(project_page)
    if source_info:
        return summarize_project_source(*source_info)
    raise ValueError("No project information provided for analysis.")

def get_release_data_and_version(url, rev=None):
    """Fetch release data and compute version string with proper logging."""
    from vibenix.ccl_log import get_logger
    ccl_logger = get_logger()
    
    ccl_logger.enter_attribute("get_release_data_from_forge", log_start=True)
    ccl_logger.write_kv("forge", "github")
    ccl_logger.write_kv("url", url)
    
    # Fetch latest release if rev not provided
    if not rev:
        rev = fetch_github_release_data(url)
        ccl_logger.write_kv("latest_gh_release_tag", rev)
    
    # Compute version based on whether we have a rev
    if rev:
        version = rev[1:] if rev.startswith('v') else rev
        ccl_logger.write_kv("extracted_version", version)
    else:
        version = None
    ccl_logger.leave_attribute(log_end=True)
    return rev, version

def run_nurl(url, rev=None):
    """Run nurl command and return the version and fetcher."""
    backoff_time = 5  # seconds
    try:
        from vibenix.ccl_log import get_logger
        ccl_logger = get_logger()
        ccl_logger.enter_attribute("pin_fetcher", log_start=True)
        
        # Get release data and version
        rev, version = get_release_data_and_version(url, rev)

        cmd = ['nurl', url, rev] if rev else ['nurl', url]
        ccl_logger.write_kv("nurl_args", " ".join(cmd[1:]))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        fetcher = result.stdout.strip()

        # Format fetcher with version
        ccl_logger.write_kv("fetcher", fetcher)
        if version:
            fetcher = fetcher.replace(version, "${version}") 
        else:
            version = "unstable-${src.rev}"
        ccl_logger.write_kv("version", version)
        
        ccl_logger.leave_attribute(log_end=True)
        return version, fetcher
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.lower()
        # Check for various rate limit indicators
        if any(indicator in error_output for indicator in ["rate limit", "429", "403", "forbidden"]):
            print(f"Rate limit/forbidden error for {url}")
            import time
            time.sleep(backoff_time)
            backoff_time *= 2  # Exponential backoff
            if backoff_time >= 360:
                coordinator_error("Exceeded maximum backoff time due to repeated rate limiting.")
                return None, "RATE_LIMITED"
        print(f"Error running nurl for {url}: {e.stderr}")
        return None, None
    except FileNotFoundError:
        print("Error: nurl command not found. Please ensure nurl is installed.")
        return None, None


def read_fetcher_file(fetcher: str) -> tuple[str, str]:
    """Read the fetcher file content."""
    from pathlib import Path
    try:
        ccl_logger = get_logger()
        ccl_logger.enter_attribute("load_fetcher", log_start=True)
        ccl_logger.write_kv("path", fetcher)

        path = Path(fetcher)
        with open(path, 'r') as f:
            # Ignore comments and empty lines
            content = "".join(line for line in f if line.strip() and not line.startswith("#")).rstrip()
        ccl_logger.write_kv("fetcher", content)

        # Instantiate fetcher to pull contents to nix store TODO theres probably definetly a better way
        cmd = [
            'nix',
            'build',
            '--impure',
            '--expr',
            f"let pkgs = (builtins.getFlake (toString ./.)).inputs.nixpkgs.legacyPackages.${{builtins.currentSystem}}; in\nwith pkgs; {content}"
        ]
        try:
            result = subprocess.run(cmd, cwd=config.template_dir, capture_output=True, text=True, check=True)
            if result.returncode != 0:
                ccl_logger.write_kv("nix_eval_error", result.stderr)
                ccl_logger.leave_attribute(log_end=True)
                raise RuntimeError(f"{result.stderr}")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            raise RuntimeError(f"Failed to evaluate project fetcher: {e}")

        # Extract version from the fetcher if present
        version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
        version = version_match.group(1) if version_match else "unstable-${src.rev}"
        ccl_logger.write_kv("version", version)
        ccl_logger.leave_attribute(log_end=True)
        return version, content
    except FileNotFoundError:
        coordinator_error(f"Fetcher file '{fetcher}' not found.")
        raise
    except Exception as e:
        coordinator_error(f"Error reading fetcher file: {e}")
        raise


def compare_template(available_builders, initial_code,
                     find_similar_builder_patterns, summary) -> str:
    """Prompt LLM to compare template with set of builders it thinks are relevant,
    present builder combinations to model, and let it make changes if needed."""
    from vibenix.tools.search_related_packages import _extract_builders

    builders = choose_builders(available_builders, summary)
    if not choose_builders:
        raise RuntimeError("Model failed to choose builders for comparison.")
    builders_set = set(builder.split(".")[-1].strip("'\"") for builder in builders) # has happened it reply with '"pkgs.(...)"'
    template_builders = _extract_builders(initial_code, available_builders) or []
    template_builders = set(builder.split(".")[-1] for builder in template_builders)
    if len(builders) > 0 and builders_set != template_builders:
        # Get builder combinations and random set of packages for each
        builder_combinations = find_similar_builder_patterns(builders)
        coordinator_message(builder_combinations)
        # Let model analyse and make changes
        compare_template_builders(view_package_contents(prompt="compare_template_builders"), builder_combinations, summary)
        initial_code = get_package_contents()
        coordinator_message(f"Finished comparing builders to template.")
    else:
        coordinator_message("Builders chosen by model match template. Skipping comparison step.")
    return initial_code


def package_project(output_dir=None, project_url=None, revision=None, fetcher=None):
    """Main coordinator function for packaging a project."""
    # Initialize CCL logger
    log_file = Path(output_dir) / "run.ccl" if output_dir else Path("run.ccl")
    ccl_logger = init_logger(log_file)
    
    # Log vibenix version info
    git_info = get_git_info()
    if git_info["commit_hash"]:
        ccl_logger.enter_attribute("vibenix_version")
        ccl_logger.write_kv("git_hash", git_info["commit_hash"])
        ccl_logger.write_kv("dirty", "true" if git_info["is_dirty"] else "false")
        ccl_logger.leave_attribute()
    
    # Step 1: Get project URL (includes welcome message)
    if not (project_url or fetcher):
        project_url = get_project_url() # Interactive mode (none)
    else: # (purl or both)
        # When URL is provided via CLI, still show welcome but skip prompt
        coordinator_message("Welcome to vibenix!")
    
    # Log model configuration
    from vibenix.model_config import get_model_config
    ccl_logger.log_model_config(get_model_config())
    # Log vibenix settings
    ccl_logger.log_vibenix_settings()

    if project_url:
        ccl_logger.write_kv("project_url", project_url)

    # Obtain the project fetcher
    if fetcher: 
        coordinator_progress(f"Using provided fetcher: {fetcher}")
        version, fetcher = read_fetcher_file(fetcher)
        if revision:
            coordinator_error("Ignoring revision parameter in favor of provided fetcher.")
    else:
        if not project_url:
            coordinator_error("No project URL nor fetcher provided, either is required for Vibenix to proceed.")
            return
        coordinator_progress("Obtaining project fetcher from the provided URL")
        version, fetcher = run_nurl(project_url, revision)

    # Step 2: Create additional (runtime-initialized) tools for model
    store_path, nixpkgs_path = get_store_path(fetcher), get_nixpkgs_source_path()
    project_functions = create_source_function_calls(store_path, "project_")
    nixpkgs_functions = create_source_function_calls(nixpkgs_path, "nixpkgs_")
    from vibenix.tools.search_related_packages import get_builder_functions, _create_find_similar_builder_patterns
    available_builders = get_builder_functions()
    find_similar_builder_patterns = _create_find_similar_builder_patterns(available_builders)
    additional_functions = project_functions + nixpkgs_functions + [get_builder_functions, find_similar_builder_patterns]
    # Initialize said tools via settings manager
    get_settings_manager().initialize_additional_tools(additional_functions)

    # Step 3: Analyze project to obtain summary used for model prompts
    if get_settings_manager().get_setting_enabled("scrape_project_page"):
        # Scrape project page
        if not project_url:
            coordinator_error("Project URL is required to scrape project page, which is enabled in Vibenix settings.")
            return
        coordinator_message(f"Scraping project page from {project_url}")
        try:
            project_page = scrape_and_process(project_url)
        except Exception as e:
            coordinator_error(f"Failed to fetch project page: {e}")
            return
        
        coordinator_message("I found the project information. Let me analyze it.")
        ccl_logger.log_project_summary_begin()
        summary = analyze_project(project_page=project_page)
        ccl_logger.log_project_summary_end(summary)
    else:
        # Use project source root's README.md + root directory file list as information sources
        coordinator_message("Using project source files to analyze the project.")
        try:
            from vibenix.tools.file_tools import get_project_source_info
            source_info = get_project_source_info(store_path)
        except Exception as e:
            coordinator_error(f"Failed to acquire project summary from source: {e}")
            return

        ccl_logger.log_project_summary_begin()
        summary = analyze_project(source_info=source_info)
        ccl_logger.log_project_summary_end(summary)

    if not summary:
        coordinator_error("Model failed to produce a project summary.")

    # Step 4: Initialize flake
    coordinator_progress("Setting up a temporary Nix flake for packaging")
    init_flake()
    coordinator_message(f"Working on temporary flake at {config.flake_dir}")
    
    ccl_logger.log_template_selected_begin()
    template_type = pick_template(summary)
    if not template_type:
        coordinator_error("Model failed to pick a template type.")
        return
    coordinator_message(f"Selected template: {template_type.value}")
    template_filename = f"{template_type.value}.nix"
    template_path = config.template_dir / template_filename
    starting_template = template_path.read_text()
    
    # Load optional notes file
    notes_filename = f"{template_type.value}.notes"
    notes_path = config.template_dir / notes_filename
    template_notes = notes_path.read_text() if notes_path.exists() else None
    ccl_logger.log_template_selected_end(template_type, starting_template, template_notes)
    template_notes = template_notes if get_settings_manager().get_setting_enabled("template_notes") else None

    # Step 6.a: Manual src setup
    coordinator_message("Setting up the src attribute in the template...")
    # Extract pname (repo name) from the fetcher
    repo_match = re.search(r'repo\s*=\s*"(.*?)"', fetcher)
    if not repo_match:
        coordinator_error("Could not extract repo name from fetcher")
        return
    pname = repo_match.group(1)
    
    initial_code = fill_src_attributes(starting_template, pname, version, fetcher)

    if get_settings_manager().get_setting_enabled("build_summary"):
        build_summary = summarize_build(summary)
        if not build_summary:
            coordinator_error("Model failed to produce a build summary.")
            return
        summary += f"\n\nBuild Summary:\n{build_summary}"

    if get_settings_manager().get_setting_enabled("compare_template_builders"):
        initial_code = compare_template(available_builders, initial_code, find_similar_builder_patterns, summary)
    coordinator_message(f"Initial package code:\n```nix\n{initial_code}\n```")

    # Step 7: Agentic loop
    coordinator_progress("Testing the initial build...")
    best = execute_build_and_add_to_stack(initial_code)

    ccl_logger.log_initial_build(view_package_contents(), best.result)
    
    from vibenix.packaging_flow.packaging_loop import packaging_loop 
    candidate, best, status = packaging_loop(
        best,
        summary,
        template_notes
    )

    # Log the raw package code before refinement or analysis
    ccl_logger.write_kv("raw_package", candidate.code)
    
    if candidate.result.success:
        coordinator_message("Build succeeded!")
        if get_settings_manager().get_setting_enabled("refinement"):
            packaging_usage = get_model_prompt_manager().get_session_usage()
            candidate = refine_package(candidate, summary, template_notes)
            ccl_logger.write_kv("refined_package", candidate.code)

            refinement_usage = get_model_prompt_manager().get_session_usage() - packaging_usage
            ccl_logger.log_refinement_cost(
                packaging_usage.calculate_cost(),
                refinement_usage.calculate_cost(),
                refinement_usage.prompt_tokens,
                refinement_usage.completion_tokens,
                refinement_usage.cache_read_tokens
            )
        
        ccl_logger.log_total_tool_cost()
        # Always log success and return, regardless of refinement outcome
        ccl_logger.log_session_end(signal=None, total_cost=get_model_prompt_manager().get_session_cost())
        close_logger()
        if output_dir:
            save_package_output(candidate.code, output_dir)
        return candidate.code  
    else:
        max_iterations = get_settings_manager().get_setting_value("packaging_loop.max_iterations")
        max_consecutive_non_build_errors = get_settings_manager().get_setting_value("packaging_loop.max_consecutive_non_build_errors")
        if status['consecutive_non_build_errors'] >= max_consecutive_non_build_errors:
            coordinator_error(f"Aborted: {status['consecutive_rebuilds_without_progress']} consecutive rebuilds without progress.")
        else:
            coordinator_error(f"Reached MAX_ITERATIONS build iteration limit of {max_iterations}.")
    
    ccl_logger.enter_attribute("analyze_failure")
    revert_packaging_to_solution(best) # TODO do this differently later, not just best
    details = analyze_package_failure(best.code, best.result.error.truncated(), summary, template_notes) # TODO best.code
    ccl_logger.write_kv("description", str(details))
    packaging_failure = classify_packaging_failure(details)
    ccl_logger.write_kv("failure_type", enum_str(packaging_failure))
    ccl_logger.leave_attribute()
    if isinstance(packaging_failure, PackagingFailure):
        coordinator_message(f"Packaging failure type: {packaging_failure}\nDetails:\n{details}\n")

    ccl_logger.log_total_tool_cost()
    ccl_logger.log_session_end(signal=None, total_cost=get_model_prompt_manager().get_session_cost())
    close_logger()
    return None


def save_package_output(code: str, output_dir: str):
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
        else:
            coordinator_message("Packaging failed. Please check the errors above.")
        print(f"Total API cost: ${get_model_prompt_manager().get_session_cost():.4f}")
    except Exception as e:
        coordinator_error(f"Unexpected error: {e}")
        from vibenix.ccl_log import get_logger
        get_logger().log_total_tool_cost()
        get_logger().log_session_end(signal=None, total_cost=get_model_prompt_manager().get_session_cost())
        close_logger()
        raise
