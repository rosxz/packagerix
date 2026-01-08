from vibenix.flake import get_package_contents
from vibenix.ui.conversation import ask_user,  coordinator_message, coordinator_error, coordinator_progress
from vibenix.nix import eval_progress, execute_build_and_add_to_stack, revert_packaging_to_solution
from vibenix.packaging_flow.model_prompts import (
    refine_code, get_feedback
)
from vibenix.ccl_log import init_logger, get_logger, close_logger, enum_str
from vibenix.errors import NixBuildErrorDiff, NixErrorKind, NixBuildResult
from vibenix.packaging_flow.Solution import Solution
from vibenix.tools.view import _view as view_package_contents
from vibenix.ui.conversation import get_ui_adapter
from vibenix.packaging_flow.packaging_loop import packaging_loop

from vibenix.packaging_flow.model_prompts import model_prompt_manager
from vibenix.nix import get_build_output_path

from vibenix import config

def get_linter_feedback() -> list[str]:
    from vibenix.flake import get_package_path
    import subprocess
    path = get_package_path()
    linters = [
        f"statix check {path}",
        f"nixpkgs-lint {path}",
        f"nil diagnostics {path}",
        f"nixf-diagnose {path}",
    ]

    feedback = []
    for cmd in linters:
        cmd = cmd.split(' ')
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip() or result.stderr.strip():
            feedback.append(f"Output from `{result.args}`:\n{result.stdout}\n{result.stderr}")
    return feedback
        

def refine_package(curr: Solution, project_page: str) -> Solution:
    """Refinement cycle to improve the packaging."""
    from vibenix.defaults import get_settings_manager
    # Max iterations for refinement's internal packaging loop (fix build errors)
    max_iterations = get_settings_manager().get_setting_value("refinement.max_iterations")
    use_chat_history = get_settings_manager().get_setting_value("refinement.chat_history")

    from vibenix.ccl_log import get_logger, close_logger
    ccl_logger = get_logger()
    ccl_logger.enter_attribute("refine_package", log_start=True)

    coordinator_message("Starting refinement process for the package.")

    chat_history = None
    if use_chat_history:
        chat_history = [] # List to keep track of (user_prompt -> final model response) over the course of refinement

    iteration = 0
    while iteration < 3: # TODO make configurable
        ccl_logger.log_iteration_start(iteration)
        ccl_logger.write_kv("code", curr.code)

        # Get feedback (VM will be started/stopped automatically by run_in_vm calls)
        linters = get_linter_feedback()
        if any(linters):
            coordinator_message("Linters have reported issues with the current packaging code. Using linter feedback.")
            feedback = "\n".join(linters)
        else:
            feedback = get_feedback(curr, project_page, chat_history=chat_history).strip()
        ccl_logger.write_kv("feedback", str(feedback))

        coordinator_message(f"Refining package based on feedback...")
        refine_code(view_package_contents(prompt="refine_code"), feedback, project_page, chat_history=chat_history)
        updated_code = get_package_contents()
        ccl_logger.write_kv("refined_code", updated_code)

        attempt = execute_build_and_add_to_stack(updated_code)
        # Verify the updated code still builds
        refining_error = None
        if not attempt.result.success:
            coordinator_error(f"Refinement caused a regression ({attempt.result.error.type}), attempting to fix errors introduced.")
            refining_error = attempt.result.error

            ccl_logger.enter_attribute("refinement_packaging_loop")
            max_iterations = get_settings_manager().get_setting_value("refinement.max_iterations")
            _, attempt, _ = packaging_loop(attempt, project_page, max_iterations)
            ccl_logger.leave_attribute()

        if not attempt.result.success:
            coordinator_message(f"Failed to implement changes based on user feedback in {max_iterations} iterations. Resetting packaging code to previous successful solution.")
            revert_packaging_to_solution(curr)
            ccl_logger.write_kv("type", attempt.result.error.type)
            ccl_logger.write_kv("error", attempt.result.error.truncated())
        else:
            if refining_error and use_chat_history:
                from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

                error_msg = f"The refined code introduced errors during build: {enum_str(refining_error.type)}.\nError details:\n{refining_error.truncated()}\n\n Please fix them."
                user_message = ModelRequest(parts=[UserPromptPart(content=error_msg)])
                model_message = ModelResponse(parts=[TextPart(content=attempt.code)])

                chat_history.append(user_message)
                chat_history.append(model_message)
                refining_error = None
            coordinator_progress("Refined packaging code successfuly builds.")
            curr = attempt
        iteration += 1

    if iteration > 0:
        ccl_logger.leave_list()

    # Close the iteration list and refine_package attribute
    ccl_logger.leave_attribute(log_end=True)
    coordinator_message("Refinement process reached its conclusion (max iterations).")
    return curr


