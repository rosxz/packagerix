"""Maintenance mode for vibenix - analyze and fix existing Nix package directories."""

from pathlib import Path
import subprocess
from typing import Optional
from vibenix.ui.logging_config import logger

from vibenix.ccl_log import init_logger, get_logger, close_logger, enum_str
from vibenix.git_info import get_git_info
from vibenix.ui.conversation import coordinator_message, coordinator_error, coordinator_progress
from vibenix.ui.conversation_templated import get_model_prompt_manager
from vibenix.flake import init_flake, get_package_contents
from vibenix.packaging_flow.model_prompts import analyze_package_failure, classify_packaging_failure, PackagingFailure
from vibenix.packaging_flow.refinement import refine_package
from vibenix import config

current_system = ""

def inject_final_attrs(package_content: str) -> str:
    """
    Inject finalAttrs into package content if it doesn't already have it.
    
    This handles the case where post-state uses finalAttrs but pre-state doesn't.
    We transform `stdenv.mkDerivation {` into `stdenv.mkDerivation (finalAttrs: {`
    and the final `}` into `})`.
    
    Returns modified package content.
    """
    import re

    # Find the builder line pattern: `word.word... {` at start of line
    # This matches patterns like `stdenv.mkDerivation {`, `buildPythonPackage {`, etc.
    match = re.search(r'^(\s*\w+(?:\.\w+)*\s*)\{', package_content, re.MULTILINE)
    if not match:
        return package_content
    
    first_brace_pos = match.end() - 1  # Position of the `{`
    
    # Find the last `}` in the content (end of the body)
    last_brace = package_content.rfind('}')
    if last_brace == -1 or last_brace <= first_brace_pos:
        return package_content
    
    # Replace first `{` with `(finalAttrs: {` and last `}` with `})`
    modified = (
        package_content[:first_brace_pos] +
        '(finalAttrs: {' +
        package_content[first_brace_pos + 1:last_brace] +
        '})'# +
        #package_content[last_brace + 1:]
    )
    
    return modified

def update_fetcher(project_url: Optional[str], revision: Optional[str]) -> str:
    """Update the fetcher in package.nix to reflect project updates.
    Runs nurl to get the fetcher for the provided version (default: latest rev) and replaces it in package.nix.
    
    Raises an error if the package uses a fetcher not supported by nurl.
    """
    coordinator_progress("Updating fetcher in package.nix")

    package_contents: str = get_package_contents()
    
    # Get list of supported fetchers from nurl
    import re
    try:
        result = subprocess.run(
            ["nurl", "-l"],
            capture_output=True,
            text=True,
            check=True,
        )
        supported_fetchers = set(result.stdout.strip().split('\n'))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to get supported fetchers from nurl: {e}")
    
    # Find which fetcher is used in the package
    fetcher_name_pattern = r"src\s+=\s+(fetch\w+)\s*\{"
    fetcher_match = re.search(fetcher_name_pattern, package_contents)
    if not fetcher_match:
        raise ValueError("Could not identify fetcher type in package.nix")
    
    fetcher_name = fetcher_match.group(1)
    
    if fetcher_name not in supported_fetchers:
        raise RuntimeError(
            f"Package uses '{fetcher_name}' which is not supported by nurl.\n"
            f"Supported fetchers: {', '.join(sorted(supported_fetchers))}\n"
            f"nurl is a key dependency of vibenix maintenance mode."
        )

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
            global current_system
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

    package_contents: str = get_package_contents()
    has_finalAttrs = "finalAttrs" in package_contents
    if not has_finalAttrs:
        package_contents = inject_final_attrs(package_contents)
        has_finalAttrs = package_contents != get_package_contents() # Whether or not we injected finalAttrs successfully

    from vibenix.packaging_flow.run import run_nurl
    version, fetcher = run_nurl(project_url, revision, finalAttrs=has_finalAttrs) # Project should be updated by default, this is maintenance mode after all

    # Update the fetcher in package.niX
    # Build regex pattern to match src = fetch{...} with repo attribute matching pname (case-insensitive)
    import re
    repo = project_url.split("/")[-1].removesuffix(".git")
    fetcher_pattern = r"src\s+=\s+(fetch[\w]+\s*\{[\s\S]*?repo\s+=\s+\"[^\"]*" + re.escape(repo) + r"[^\"]*\"[\s\S]*?\});"
    # TODO check how much identation previous fetcher had to match or something
    fetcher_match = re.search(fetcher_pattern, package_contents, re.IGNORECASE)
    fetcher_content = ""
    if fetcher_match:
        fetcher_content = fetcher_match.group(1)
        coordinator_message(f"Found fetcher with repo matching '{repo}'")
    else:
        coordinator_error(f"No fetcher found with repo matching '{repo}'")
        raise ValueError(f"Could not find fetcher with repo matching '{repo}' in flake.nix")

    coordinator_message(f"Previous fetcher:\n```nix\n{fetcher_content}\n```\nUpdating fetcher to version: {version}")
    # Indent all lines after the first by 2 spaces
    lines = fetcher.split('\n')
    if len(lines) > 1:
        fetcher = lines[0] + '\n' + '\n'.join('  ' + line for line in lines[1:])
    new_package_contents = package_contents.replace(fetcher_content, fetcher)
    
    # Also update the version = "..." line
    version_pattern = r'(version\s*=\s*)"([^"]+)"'
    version_match = re.search(version_pattern, new_package_contents)
    if version_match:
        old_version = version_match.group(2)
        coordinator_message(f"Updating version: {old_version} -> {version}")
        new_package_contents = re.sub(version_pattern, rf'\1"{version}"', new_package_contents, count=1)
    else:
        coordinator_error(f"No version = \"...\" found in package.nix, skipping version update")
        raise ValueError("Could not find version = \"...\" line in package.nix")
    
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
    ccl_logger.enter_attribute("load_fetcher", log_start=True)
    ccl_logger.write_kv("fetcher", fetcher_contents)

    global current_system
    # Instantiate fetcher to pull contents to nix store TODO theres probably definetly a better way
    cmd = [
        'nix',
        'build',
        '--impure',
        f'.#packages.{current_system}.default.src',
    ]
    try:
        result = subprocess.run(cmd, cwd=config.flake_dir, capture_output=True, text=True, check=True)
        if result.returncode != 0:
            ccl_logger.write_kv("nix_eval_error", result.stderr)
            ccl_logger.leave_attribute(log_end=True)
            raise RuntimeError(f"{result.stderr}")
    except subprocess.CalledProcessError as e:
        error_details = e.stderr if hasattr(e, 'stderr') else str(e)
        ccl_logger.write_kv("nix_eval_error", error_details)
        ccl_logger.leave_attribute(log_end=True)
        raise RuntimeError(f"Failed to evaluate project fetcher:\n{error_details}")

def save_package_output(package_directory: Path, output_dir: str) -> None:
    """Save the fixed package.nix and accompanying files to the output directory.
    
    Only copies essential files: package.nix, flake.nix, flake.lock, and run.ccl.
    Excludes build artifacts like result symlinks, vm-task directory, and packages.nix.
    """
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # List of files/patterns to exclude from output
    exclude_items = {'result', 'vm-task', 'packages.nix', '.git', '.gitignore'}

    def ignore_patterns(dir, contents):
        """Ignore build artifacts and git files."""
        return [c for c in contents if c in exclude_items or c.startswith(".git")]

    # Copy files from package_directory to output_path
    import shutil
    for item in package_directory.iterdir():
        # Skip excluded items
        if item.name in exclude_items or item.name.startswith(".git"):
            continue
        # Skip symlinks (like result)
        if item.is_symlink():
            continue
            
        dest = output_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True, ignore=ignore_patterns)
        else:
            shutil.copy2(item, dest)

    coordinator_message(f"Saved updated package.nix to: {output_path / 'package.nix'}")

def create_nixpkgs_function_calls(initial_path: str):
    """
    Create all the file tools, but wrap them with a method that updates
    the root_dir variable of the class to the current nixpkgs outPath.
    """
    from vibenix.tools.file_tools import create_source_function_calls
    funcs = create_source_function_calls(
        store_path=initial_path,
        prefix="nixpkgs_",
        dynamic_path=True
    )
    funcs, update_path = funcs[:-1], funcs[-1]
    
    import functools
    def decorate_dynamic_path_update(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from vibenix.packaging_flow.run import get_nixpkgs_source_path
            update_path(get_nixpkgs_source_path())
            result = func(*args, **kwargs)
            return result
        return wrapper

    decorated_funcs = [decorate_dynamic_path_update(f) for f in funcs]
    return decorated_funcs


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

    def _validate_required_file(filename: str) -> Path:
        file_path = maintenance_path / filename

        if not file_path.exists():
            logger.error(f"Required maintenance file missing: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            logger.error(f"Expected a file but found a directory at: {file_path}")
            raise ValueError(f"Expected a file, got a directory: {file_path}")

        return file_path

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

    package_nix_path = _validate_required_file("package.nix")
    try:
        flake_lock_path = _validate_required_file("flake.lock")
    except FileNotFoundError:
        flake_lock_path = None
    try:
        flake_nix_path = _validate_required_file("flake.nix")
    except FileNotFoundError:
        flake_nix_path = None

    coordinator_message(f"Validated required files: flake.nix at {flake_nix_path}, package.nix at {package_nix_path}")
    if flake_lock_path is None:
        coordinator_message("flake.lock not provided; continuing without it") # TODO make
    if flake_nix_path is None:
        coordinator_message("flake.nix not provided; continuing without it") # TODO make

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
        # upgrade_lock_file() # match closest nixpkgs release # Not doing this anymore

    # Create additional (runtime-initialized) tools for model
    from vibenix.packaging_flow.run import get_nixpkgs_source_path, create_source_function_calls, get_store_path
    store_path = get_store_path(fetcher)
    nixpkgs_path = get_nixpkgs_source_path()
    project_functions = create_source_function_calls(store_path, "project_")
    nixpkgs_functions = create_nixpkgs_function_calls(nixpkgs_path) # Dynamic nixpkgs path update
    from vibenix.tools.search_related_packages import get_builder_functions, \
     _create_find_similar_builder_patterns
    find_similar_builder_patterns = _create_find_similar_builder_patterns(use_cache=True)
    additional_functions = project_functions + nixpkgs_functions + [get_builder_functions, find_similar_builder_patterns]
    # Initialize said tools via settings manager
    from vibenix.ui.conversation_templated import get_settings_manager
    get_settings_manager().initialize_additional_tools(additional_functions)

    # Analyze project to obtain summary used for model prompts
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

    # Agentic loop
    coordinator_progress("Testing the initial build...")
    from vibenix.nix import execute_build_and_add_to_stack, revert_packaging_to_solution
    best = execute_build_and_add_to_stack(get_package_contents())

    from vibenix.tools.view import _view as view_package_contents 
    ccl_logger.log_initial_build(view_package_contents(), best.result)
    
    from vibenix.packaging_flow.packaging_loop import packaging_loop 
    candidate, best, status = packaging_loop(
        best,
        summary,
        maintenance_mode=True
    )

    # Log the raw package code before refinement or analysis
    ccl_logger.write_kv("raw_package", candidate.code)
    
    if candidate.result.success:
        coordinator_message("Build succeeded!")
        if get_settings_manager().get_setting_enabled("refinement.enabled"):
            packaging_usage = get_model_prompt_manager().get_session_usage()
            candidate = refine_package(candidate, summary, output_dir)
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
        if output_dir:
            from vibenix.flake import get_package_path
            package_directory = Path(get_package_path()).parent
            save_package_output(package_directory, output_dir)
        close_logger()
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
    details = analyze_package_failure(best.code, best.result.error.truncated(), summary) # TODO best.code
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

