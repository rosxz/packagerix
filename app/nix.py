import subprocess

from app.config import flake_dir, error_stack
from pydantic import BaseModel

import git

from typing import Optional

from app.flake import update_flake
from app.logging_config import logger

def search_nixpkgs_for_package(query: str) -> str:
    """search the nixpkgs repository of Nix code for the given package"""

    result = subprocess.run(["nix", "search", "nixpkgs", query], text=True, capture_output=True)
    if result.returncode == 0:
        return result.stdout
    else:
        return f"no results found for query '{query}'"

def invoke_build() -> subprocess.CompletedProcess :
    return subprocess.run(["nix", "build", flake_dir], text=True, capture_output=True)


def get_last_ten_lines(s : str) -> str:
    lines = s.split('\n')
    return '\n'.join(lines[-30:])

from enum import Enum

class Error(BaseModel):
    class ErrorType(Enum):
        REGRESS = (1, "error not resolved - build fails earlier")
        EVAL_ERROR = (2, "code failed to evaluate")
        PROGRESS = (3, "error resolved - build fails later")

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

    while True:
        try:
            # Ask the user for their choice
            choice = int(input("Please pick a number corresponding to your choice: "))

            # Check if the choice is within the range
            if 1 <= choice <= len(Error.ErrorType):
                break
            else:
                logger.warning("Invalid choice. Please choose a number from the list.")

        except ValueError:
            # Handle the case where the input is not an integer
            logger.warning("Invalid input. Please enter a number.")

    # Process the choice
    errorType = Error.ErrorType.from_id(choice)
    logger.info(f"You have chosen: {errorType.description}")
    return Error(type=errorType, error_message=error_message_trunc)


def test_updated_code(updated_code: str) -> Optional[Error]:
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
        return eval_progress()
        # if errorType == Error.ErrorType.REGRESS:
        #     # retry in current context
            
        # elif errorType == Error.ErrorType.EVAL_ERROR:
        #     # try to fix error in current context
        # elif errorType == Error.ErrorType.PROGRESS:
        #     # move to next iteration
        # else:
        #     throw ValueError("unknown error type")
