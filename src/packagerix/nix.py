import subprocess

from packagerix.config import flake_dir, error_stack
from pydantic import BaseModel

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

def invoke_build() -> subprocess.CompletedProcess:
    # First, evaluate the flake to get the derivation path
    # If this fails, it's an evaluation error
    eval_result = subprocess.run(
        ["nix", "path-info", "--derivation", f"{flake_dir}#default"],
        text=True,
        capture_output=True
    )
    
    if eval_result.returncode != 0:
        return eval_result
    
    derivation_path = eval_result.stdout.strip()

    build_result = subprocess.run(
        ["nix", "build", derivation_path, "--no-link"],
        text=True,
        capture_output=True
    )

    log_result = subprocess.run(
        ["nix", "log", derivation_path],
        text=True,
        capture_output=True
    )
    
    if log_result.returncode != 0:
        # This is unexpected - we should always be able to get logs after a build
        # Except if the build of a dependency failed
        raise RuntimeError(f"Failed to retrieve build logs for {derivation_path}: {log_result.stderr}")

    return subprocess.CompletedProcess(
        args=build_result.args,
        returncode=build_result.returncode,
        stdout=log_result.stdout,
        stderr=log_result.stderr
    )


def get_last_ten_lines(s : str) -> str:
    lines = s.split('\n')
    return '\n'.join(lines[-30:])

from enum import Enum

class Error(BaseModel):
    class ErrorType(Enum):
        REGRESS = (1, "error not resolved - build fails earlier")
        EVAL_ERROR = (2, "code failed to evaluate")
        PROGRESS = (3, "error resolved - build fails later")
        HASH_MISMATCH = (4, "hash mismatch - needs correct hash to be filled in")

        def __init__(self, id, description):
            self.id = id
            self.description = description

        @classmethod
        def from_id(cls, id):
            for case in cls:
                if case.id == id:
                    return case
            raise ValueError(f"No case with id {id}")
    type: ErrorType
    error_message: str

# read build log of previous step and this step
# to evalute if the model made progress towards building the project
# this is done by counting magical phrases in the build output like
# "comiling ..." 
def eval_initial_build() -> Error:
    """Evaluate the initial build - look for hash mismatch which indicates progress."""
    completed_process = error_stack[-1]
    error_message = completed_process.stderr
    
    # Check if this is a hash mismatch error (indicates template was filled correctly)
    if "hash mismatch" in error_message.lower() or "expected sha256" in error_message.lower():
        logger.info("✅ Initial build shows hash mismatch - template was filled correctly!")
        # Return Error object for LLM to fix the hash
        return Error(type=Error.ErrorType.HASH_MISMATCH, error_message=error_message)
    else:
        logger.info("❌ Initial build failed with non-hash error")
        return Error(type=Error.ErrorType.EVAL_ERROR, error_message=error_message)

# a significantly higher number of magical phrases indicates progress
# an about equal amount goes to an llm to break the tie using same_build_error with the two tails of the two build logs
def eval_progress() -> Error:
    error_message = error_stack[-1].stderr
    error_message_trunc = f"\n```\n{get_last_ten_lines(error_stack[-1].stderr)}\n```\n"
    prev_error_message_trunc = get_last_ten_lines(error_stack[-2].stderr)
    logger.info(f"previous error: {prev_error_message_trunc}")

    logger.info(f"new error: {error_message_trunc}")

    repo = git.Repo(flake_dir.as_posix())
    logger.info(repo.commit().diff())

    # Display the sentences with numbers
    for errorType in Error.ErrorType:
        logger.info(f"{errorType.id}. {errorType.description}")

    # Use coordinator pattern to get user choice
    from packagerix.packaging_flow.user_prompts import evaluate_build_progress
    choice_str = evaluate_build_progress(prev_error_message_trunc, error_message_trunc)
    choice = int(choice_str)

    # Process the choice
    errorType = Error.ErrorType.from_id(choice)
    logger.info(f"You have chosen: {errorType.description}")
    return Error(type=errorType, error_message=error_message_trunc)


def test_updated_code(updated_code: str, is_initial_build: bool = False) -> Optional[Error]:
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
    if result.returncode == 0:
        return None
    else:
        if is_initial_build:
            return eval_initial_build()
        else:
            return eval_progress()
        # if errorType == Error.ErrorType.REGRESS:
        #     # retry in current context
            
        # elif errorType == Error.ErrorType.EVAL_ERROR:
        #     # try to fix error in current context
        # elif errorType == Error.ErrorType.PROGRESS:
        #     # move to next iteration
        # else:
        #     throw ValueError("unknown error type")
