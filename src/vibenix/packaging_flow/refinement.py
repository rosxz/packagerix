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

def refine_package(curr: Solution, project_page: str, template_notes: str) -> Solution:
    """Refinement cycle to improve the packaging."""
    from vibenix.defaults import get_settings_manager
    # Max iterations for refinement's internal packaging loop (fix build errors)
    max_iterations = get_settings_manager().get_setting_value("refinement.max_iterations")
    use_chat_history = get_settings_manager().get_setting_value("refinement.chat_history")

    from vibenix.ccl_log import get_logger, close_logger
    ccl_logger = get_logger()
    ccl_logger.enter_attribute("refine_package", log_start=True)

    coordinator_message("Starting refinement process for the package.")
    iteration = 0
    while True:
        if use_chat_history:
            chat_history = [] # List to keep track of (user_prompt -> final model response) over the course of refinement
            # We reset it for each feedback from user
        else:
            chat_history = None

        # Prompt user for package error (if any) to proceed with refinement
        feedback_input = get_ui_adapter().ask_user_multiline(f'''The flake containing the package is present at '{config.flake_dir}'.
Build output should be present at '{get_build_output_path()}'.
Please provide feedback on the current packaging code (press CTRL-D to finish): ''')
        if not feedback_input.strip():
            coordinator_message("No further feedback provided, ending refinement process.")
            break
        feedback = feedback_input.strip()

        while True: # while the feedback isn't fully addressed (avoid reprompting user), regardless of build success
            ccl_logger.log_iteration_start(iteration)
            ccl_logger.write_kv("code", curr.code)

            ccl_logger.write_kv("feedback", str(feedback))
            coordinator_message(f"Refining package based on user feedback...")
            refine_code(view_package_contents(prompt="refine_code"), feedback, project_page, chat_history=chat_history)

            updated_code = get_package_contents()
            ccl_logger.write_kv("refined_code", updated_code)
            attempt = execute_build_and_add_to_stack(updated_code)

            refining_error = attempt.result.error
            # Verify the updated code still builds
            while not attempt.result.success:
                coordinator_error(f"Refinement caused a regression ({attempt.result.error.type}), attempting to fix errors introduced.")

                ccl_logger.enter_attribute("refinement_fix")
                max_iterations = get_settings_manager().get_setting_value("refinement.max_iterations")
                _, attempt, _ = packaging_loop(attempt, project_page, template_notes, max_iterations)
                ccl_logger.leave_attribute()

                if not attempt.result.success:
                    user_choice = get_ui_adapter().ask_user(f"Failed to implement changes based on user feedback in {max_iterations} iterations. Keep trying (or revert to previous state) ? (y/N): ")
                    if user_choice.strip().lower() != 'y':
                        coordinator_message("Resetting packaging code to previous successful solution.")
                        revert_packaging_to_solution(curr)
                        ccl_logger.write_kv("type", attempt.result.error.type)
                        ccl_logger.write_kv("error", attempt.result.error.truncated())
                        break

            if attempt.result.success:
                if refining_error and use_chat_history:
                    from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

                    error_msg = f"The refined code introduced a errors during build: {enum_str(refining_error.type)}.\nError details:\n{refining_error.truncated()}\n\n Please fix them."
                    user_message = ModelRequest(parts=[UserPromptPart(content=error_msg)])
                    model_message = ModelResponse(parts=[TextPart(content=attempt.code)])

                    chat_history.append(user_message)
                    chat_history.append(model_message)
                    refining_error = None

                coordinator_progress("Refined packaging code successfuly builds.")
                coordinator_message(f'''The flake containing the package is present at '{config.flake_dir}'.
Build output should be present at '{get_build_output_path()}'.''')
                user_choice = get_ui_adapter().ask_user(f"Did the feedback/issue get fixed? (Y/n): ")
                if user_choice.strip().lower() != 'n':
                    curr = attempt
                    iteration += 1
                    break
                else:
                    feedback = "The current packaging expression does not fully or partially resolve the feedback received, try again."
            iteration += 1

    if iteration > 0:
        ccl_logger.leave_list()

    # Close the iteration list and refine_package attribute
    ccl_logger.leave_attribute(log_end=True)
    coordinator_message("Refinement process reached its conclusion (max iterations).")
    return curr


