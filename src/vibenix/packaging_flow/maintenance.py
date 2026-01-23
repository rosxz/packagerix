"""Maintenance mode for vibenix - analyze and fix existing Nix package directories."""

from pathlib import Path
import subprocess
from typing import Optional
from vibenix.ui.logging_config import logger
from magika import Magika

from vibenix.ccl_log import init_logger, get_logger, close_logger, enum_str
from vibenix.git_info import get_git_info
from vibenix.ui.conversation import coordinator_message, coordinator_error, coordinator_progress
from vibenix.flake import init_flake, get_package_contents
from vibenix import config


def update_fetcher(project_url: Optional[str], revision: Optional[str]) -> str:
    """Update the fetcher in package.nix to reflect project updates.
    Runs nurl to get the fetcher for the provided version (default: latest rev) and replaces it in package.nix."""
    coordinator_progress("Updating fetcher in flake.nix and flake.lock")

    def get_project_url() -> str:
        # The pre-existing package NEEDS to evaluate correctly
        def _normalize_project_url(url: str) -> str:
            """Keep only scheme + host + owner + repo; drop deeper paths."""
            parts = url.split("/")
            if len(parts) >= 5:
                return "/".join(parts[:5]).rstrip("/")
            return url.rstrip("/")

        try:
            system_result = subprocess.run(
                [
                    "nix",
                    "eval",
                    "--raw",
                    "--impure",
                    "--expr",
                    "builtins.currentSystem",
                ],
                cwd=config.flake_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            current_system = system_result.stdout.strip()

            result = subprocess.run(
                [
                    "nix",
                    "eval",
                    "--raw",
                    f".#packages.{current_system}.default.src.url",
                ],
                cwd=config.flake_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.returncode != 0:
                ccl_logger = get_logger()
                ccl_logger.write_kv("nix_eval_error", result.stderr)
                ccl_logger.leave_attribute(log_end=True)
                raise RuntimeError(f"{result.stderr}")

            project_url = result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            raise RuntimeError(f"Failed to evaluate project fetcher: {e}")

        # Normalize: keep only https://forge/owner/repo (TODO wont work with forges on subpaths)
        project_url = _normalize_project_url(project_url)
        return project_url

    if not project_url:
        project_url = get_project_url()

    from vibenix.packaging_flow.run import run_nurl
    version, fetcher = run_nurl(project_url, revision)

    # Update the fetcher in package.nix
    package_contents: str = get_package_contents()
    # Build regex pattern to match src = fetch{...} with repo attribute matching pname (case-insensitive)
    import re
    repo = project_url.split("/")[-1]
    fetcher_pattern = rf"src\s+=\s+(fetch[\w]+\s+\{{\n(?:.*\n)*?\s+repo\s+=\s+\"[^\"]*{re.escape(repo)}[^\"]*\"\s*;\n(?:.*\n)*?\}})"
    fetcher_match = re.search(fetcher_pattern, package_contents, re.IGNORECASE | re.MULTILINE)
    fetcher_content = ""
    if fetcher_match:
        fetcher_content = fetcher_match.group(1)
        coordinator_message(f"Found fetcher with repo matching '{repo}'")
    else:
        coordinator_error(f"No fetcher found with repo matching '{repo}'")
        raise ValueError(f"Could not find fetcher with repo matching '{repo}' in flake.nix")

    new_package_contents = package_contents.replace(fetcher_content, fetcher)
    from vibenix.flake import update_flake
    update_flake(new_package_contents) # TODO rename update_flake to update_package
    return fetcher


def update_lock_file() -> None:
    """Update the flake.lock file using `nix flake update`."""
    coordinator_progress("Updating flake.lock file using `nix flake update`")
    # TODO only update nixpkgs input
    try:
        result = subprocess.run(
            [
                "nix",
                "flake",
                "update",
            ],
            cwd=config.flake_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        if result.returncode != 0:
            ccl_logger = get_logger()
            ccl_logger.write_kv("nix_flake_update_error", result.stderr)
            ccl_logger.leave_attribute(log_end=True)
            raise RuntimeError(f"{result.stderr}")

        coordinator_message("Successfully updated flake.lock file.")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        raise RuntimeError(f"Failed to update flake.lock file: {e}")

def fetch_project_src(fetcher_contents: str) -> None:
    """Ensure the project source is fetched to the Nix store."""
    coordinator_progress("Fetching project source to Nix store")
    ccl_logger = get_logger()
    ccl_logger.write_kv("fetcher", fetcher_contents)

    # Instantiate fetcher to pull contents to nix store TODO theres probably definetly a better way
    cmd = [
        'nix',
        'build',
        '--impure',
        '--expr',
        f"let pkgs = (builtins.getFlake (toString ./.)).inputs.nixpkgs.legacyPackages.${{builtins.currentSystem}}; in\nwith pkgs; {fetcher_contents}"
    ]
    try:
        result = subprocess.run(cmd, cwd=config.flake_dir, capture_output=True, text=True, check=True)
        if result.returncode != 0:
            ccl_logger.write_kv("nix_eval_error", result.stderr)
            ccl_logger.leave_attribute(log_end=True)
            raise RuntimeError(f"{result.stderr}")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        raise RuntimeError(f"Failed to evaluate project fetcher: {e}")


def run_maintenance(maintenance_dir: str, output_dir: Optional[str] = None,
                    revision: Optional[str] = None, upgrade_lock: bool = False,
                    update_lock: bool = True) -> Optional[str]:
    """Run maintenance mode on an existing Nix package directory.

    This mode is for analyzing and fixing existing package directories that
    contain flake.nix and package.nix (flake.lock optional), rather than
    packaging new projects from scratch.

    Args:
        maintenance_dir: Directory containing the Nix files to analyze/fix
        output_dir: Directory to save the fixed package.nix file
        revision: Optional project revision to upgrade to
        upgrade_lock: Whether to upgrade/bump the nixpkgs release used
        update_lock: Whether to update the flake.lock file if present
    """
    maintenance_path = Path(maintenance_dir).resolve()

    if not maintenance_path.exists():
        logger.error(f"Maintenance directory not found: {maintenance_path}")
        raise FileNotFoundError(f"Directory not found: {maintenance_path}")

    if not maintenance_path.is_dir():
        logger.error(f"Maintenance path must be a directory, not a file: {maintenance_path}")
        raise ValueError(f"Expected a directory, got a file: {maintenance_path}")

    magika = Magika()

    def _validate_required_file(filename: str, expected_suffix: str) -> Path:
        file_path = maintenance_path / filename

        if not file_path.exists():
            logger.error(f"Required maintenance file missing: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            logger.error(f"Expected a file but found a directory at: {file_path}")
            raise ValueError(f"Expected a file, got a directory: {file_path}")

        if file_path.suffix != expected_suffix:
            logger.error(f"Unexpected extension for {filename}: {file_path.suffix}")
            raise ValueError(f"Expected {expected_suffix} extension for {filename}, got: {file_path.suffix}")

        logger.info(f"Verifying {filename} using Magika: {file_path}")
        result = magika.identify_path(file_path)
        logger.info(f"Magika detection for {filename}: type={result.output.ct_label}, confidence={result.score:.2%}, is_text={result.output.is_text}")

        if not result.output.is_text:
            logger.error(f"{filename} is not a text file: {file_path}")
            raise ValueError(f"Expected a text file for {filename}, but Magika detected: {result.output.ct_label}")

        if result.output.ct_label.lower() not in ["nix", "unknown", "generic text document", "code"]:
            logger.warning(f"{filename} may not be a Nix file. Detected as: {result.output.ct_label} (confidence: {result.score:.2%})")

        return file_path

    ## Initial Vibenix messages
    # Initialize CCL logger
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        log_file = output_path / "run.ccl"
    else:
        log_file = Path("run.ccl")
    ccl_logger = init_logger(log_file)

    # Log vibenix version info
    git_info = get_git_info()
    if git_info["commit_hash"]:
        ccl_logger.enter_attribute("vibenix_version")
        ccl_logger.write_kv("git_hash", git_info["commit_hash"])
        ccl_logger.write_kv("dirty", "true" if git_info["is_dirty"] else "false")
        ccl_logger.leave_attribute()

    coordinator_message("Welcome to vibenix!") ###

    flake_nix_path = _validate_required_file("flake.nix", ".nix")
    package_nix_path = _validate_required_file("package.nix", ".nix")
    try:
        flake_lock_path = _validate_required_file("flake.lock", ".lock")
    except FileNotFoundError:
        flake_lock_path = None

    coordinator_message(f"Validated required files: flake.nix at {flake_nix_path}, package.nix at {package_nix_path}")
    if flake_lock_path is None:
        coordinator_message("flake.lock not provided; continuing without it") # TODO make

    coordinator_message(f"Starting maintenance mode for: {maintenance_path}")

    # Log model configuration
    from vibenix.model_config import get_model_config
    ccl_logger.log_model_config(get_model_config())
    # Log vibenix settings
    ccl_logger.log_vibenix_settings()

    # Initialize flake early (needed for fetcher evaluation in CSV mode)
    coordinator_progress("Setting up a temporary Nix flake for packaging")
    init_flake(reference_dir=maintenance_path)
    coordinator_message(f"Working on temporary flake at {config.flake_dir}")

    fetcher = update_fetcher(None, revision) # Update package src in the package.nix
    fetch_project_src(fetcher) # Ensure project source is in nix store
    if update_lock:
        update_lock_file()
        # upgrade_lock_file() # TODO match closest nixpkgs release

    # Step 2: Create additional (runtime-initialized) tools for model
    from vibenix.packaging_flow.run import get_nixpkgs_source_path, create_source_function_calls, get_store_path
    store_path = get_store_path(fetcher)
    nixpkgs_path = get_nixpkgs_source_path()
    project_functions = create_source_function_calls(store_path, "project_")
    nixpkgs_functions = create_source_function_calls(nixpkgs_path, "nixpkgs_")
    from vibenix.tools.search_related_packages import get_builder_functions, \
     _create_find_similar_builder_patterns
    find_similar_builder_patterns = _create_find_similar_builder_patterns(use_cache=True)
    additional_functions = project_functions + nixpkgs_functions + [get_builder_functions, find_similar_builder_patterns]
    # Initialize said tools via settings manager
    from vibenix.ui.conversation_templated import get_settings_manager
    get_settings_manager().initialize_additional_tools(additional_functions)

    # Step 3: Analyze project to obtain summary used for model prompts
    # Use project source root's README.md + root directory file list as information sources
    coordinator_message("Using project source files to analyze the project.")
    try:
        from vibenix.tools.file_tools import get_project_source_info
        source_info = get_project_source_info(store_path)
    except Exception as e:
        coordinator_error(f"Failed to acquire project summary from source: {e}")
        return

    ccl_logger.log_project_summary_begin()
    from vibenix.packaging_flow.run import analyze_project
    summary = analyze_project(source_info=source_info) # TODO add current packaging code as context?
    ccl_logger.log_project_summary_end(summary)

    if not summary:
        coordinator_error("Model failed to produce a project summary.")

    # Step 7: Agentic loop
    coordinator_progress("Testing the initial build...")
    from vibenix.nix import execute_build_and_add_to_stack, revert_packaging_to_solution
    best = execute_build_and_add_to_stack(get_package_contents())

    from vibenix.tools.view import _view as view_package_contents 
    ccl_logger.log_initial_build(view_package_contents(), best.result)
    
    from vibenix.packaging_flow.packaging_loop import packaging_loop 
    candidate, best, status = packaging_loop(
        best,
        summary,
    )

    return None
