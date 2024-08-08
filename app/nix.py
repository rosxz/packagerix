import subprocess

from config import flake_dir, error_stack

import git

from flake import update_flake

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
# read build log of previous step and this step
# to evalute if the model made progress towards building the project
# this is done by counting magical phrases in the build output like
# "comiling ..." 
# a significantly higher number of magical phrases indicates progress
# an about equal amount goes to an llm to break the tie using same_build_error with the two tails of the two build logs
def eval_progress() -> str :

    error_message = f"\n```\n{get_last_ten_lines(error_stack[-1].stderr)}\n```\n"
    prev_error_message = get_last_ten_lines(error_stack[-2].stderr)
    print(f"previous error: {prev_error_message}")

    print(f"new error: {error_message}")

    repo = git.Repo(flake_dir.as_posix())
    print(repo.commit().diff())

    # lets do this the human way for now
    errors = [
        f"error not resolved - build fails earlier: {error_message}",
        f"error resolved - build fails later. please fix the nwe error: {error_message}",
        f"code failed to evaluate - please fix the error: {error_message}",
    ]

    # Display the sentences with numbers
    for index, error in enumerate(errors, start=1):
        first_line = error.split('\n')[0]
        print(f"{index}. {first_line}")

    while True:
        try:
            # Ask the user for their choice
            choice = int(input("Please pick a number corresponding to your choice: "))

            # Check if the choice is within the range
            if 1 <= choice <= len(errors):
                break
            else:
                print("Invalid choice. Please choose a number from the list.")

        except ValueError:
            # Handle the case where the input is not an integer
            print("Invalid input. Please enter a number.")

    # Process the choice
    result = errors[choice - 1]
    print(f"You have chosen: {result}")
    return result


def test_updated_code(updated_code: str) -> str:
    """build updated Nix code"""

    update_flake(updated_code)
    result = invoke_build()
    error_stack.append(result)
    # now check if we made progress
    # if we made progress we should
    # return and re-start with the next step
    # if we did not make progress we should return
    # the error to the LLM
    if result.returncode == 0:
        return "The build succeeded. Your job is done."
    else:
        return eval_progress()
