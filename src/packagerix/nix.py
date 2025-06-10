import subprocess

from packagerix.config import flake_dir, error_stack
from packagerix.packaging_flow.model_prompts import evaluate_progress
from packagerix.errors import NixBuildResult, NixError, NixErrorKind, NixBuildErrorDiff

import git

from typing import Optional

from packagerix.flake import update_flake
from packagerix.ui.logging_config import logger

def search_nixpkgs_for_package(query: str) -> str:
    """search the nixpkgs repository of Nix code for the given package"""

    result = subprocess.run(["nix", "search", "nixpkgs", query], text=True, capture_output=True)
    if result.returncode == 0:
        return result.stdout
    else:
        return f"no results found for query '{query}'"

def invoke_build() -> NixBuildResult:
    # First, evaluate the flake to get the derivation path
    # If this fails, it's an evaluation error
    eval_result = subprocess.run(
        ["nix", "path-info", "--derivation", f"{flake_dir}#default"],
        text=True,
        capture_output=True
    )
    
    if eval_result.returncode != 0:
        return NixBuildResult(
            success=False,
            error=NixError(type=NixErrorKind.EVAL_ERROR, error_message=eval_result.stderr)
        )
    
    derivation_path = eval_result.stdout.strip()

    build_result = subprocess.run(
        ["nix", "build", derivation_path, "--no-link"],
        text=True,
        capture_output=True
    )

    # If build succeeded, return success
    if build_result.returncode == 0:
        return NixBuildResult(success=True)

    # Build failed, check if it's a hash mismatch before getting logs
    if "hash mismatch in fixed-output derivation" in build_result.stderr:
        return NixBuildResult(
            success=False,
            error=NixError(type=NixErrorKind.HASH_MISMATCH, error_message=build_result.stderr)
        )

    # Not a hash mismatch, get logs for build error
    log_result = subprocess.run(
        ["nix", "log", derivation_path],
        text=True,
        capture_output=True
    )
    
    if log_result.returncode != 0:
        # This is unexpected - we should always be able to get logs after a build
        # Except if the build of a dependency failed
        raise RuntimeError(f"Failed to retrieve build logs for {derivation_path}: {log_result.stderr}")

    return NixBuildResult(
        success=False,
        error=NixError(type=NixErrorKind.BUILD_ERROR, error_message=log_result.stdout)
    )


def get_last_ten_lines(s : str) -> str:
    lines = s.split('\n')
    return '\n'.join(lines[-30:])


# read build log of previous step and this step
# to evalute if the model made progress towards building the project
# this is done by counting magical phrases in the build output like
# "comiling ..." 
def eval_initial_build() -> NixError:
    """Evaluate the initial build - look for hash mismatch which indicates progress."""
    build_result = error_stack[-1]
    error_message = build_result.error.error_message
    
    # Check if this is a hash mismatch error (indicates template was filled correctly)
    if "hash mismatch" in error_message.lower() or "expected sha256" in error_message.lower():
        logger.info("✅ Initial build shows hash mismatch - template was filled correctly!")
        # Return NixError object for LLM to fix the hash
        return NixError(type=NixErrorKind.HASH_MISMATCH, error_message=error_message)
    else:
        logger.info("❌ Initial build failed with non-hash error")
        return NixError(type=NixErrorKind.EVAL_ERROR, error_message=error_message)

# a significantly higher number of magical phrases indicates progress
# an about equal amount goes to an llm to break the tie using same_build_error with the two tails of the two build logs
def eval_progress() -> NixBuildErrorDiff:
    current_result = error_stack[-1]
    prev_result = error_stack[-2]
    
    error_message = current_result.error.error_message
    error_message_trunc = f"\n```\n{get_last_ten_lines(current_result.error.error_message)}\n```\n"
    prev_error_message_trunc = get_last_ten_lines(prev_result.error.error_message)
    logger.info(f"previous error: {prev_error_message_trunc}")

    logger.info(f"new error: {error_message_trunc}")

    repo = git.Repo(flake_dir.as_posix())
    logger.info(repo.commit().diff())

    return evaluate_progress(prev_error_message_trunc, error_message_trunc)

def test_updated_code(updated_code: str, is_initial_build: bool = False) -> Optional[NixError]:
    """build updated Nix code"""

    update_flake(updated_code)
    result = invoke_build()
    error_stack.append(result)
    # if this is an eval error we should stay in the current context and try to fix it
    # if 



    # now check if we made progress
    # if we made progress we should
    # return and re-start with the next step
    # if we did not make progress we should return
    # the error to the LLM
    if result.success:
        return None
    else:
        if is_initial_build:
            return eval_initial_build()
        else:
            return eval_progress()
        # if errorType == ErrorType.REGRESS:
        #     # retry in current context
            
        # elif errorType == ErrorType.EVAL_ERROR:
        #     # try to fix error in current context
        # elif errorType == ErrorType.PROGRESS:
        #     # move to next iteration
        # else:
        #     throw ValueError("unknown error type")
