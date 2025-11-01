"""All model prompts for vibenix.

This module contains all functions that interact with the AI model using template-based prompts.
"""

from enum import Enum
from typing import List, Optional

from vibenix.ui.conversation import ask_user,  coordinator_message, coordinator_error, coordinator_progress
from vibenix.template.template_types import TemplateType
from vibenix.ui.conversation_templated import model_prompt_manager
from vibenix.tools import (
    search_nixpkgs_for_package_semantic,
    search_nixpkgs_for_package_literal,
    search_nix_functions,
    search_nixpkgs_for_file,
    search_nixpkgs_manual_documentation,
    replace,
    insert_line_after,
    read_file,
)
from vibenix.errors import NixBuildErrorDiff, LogDiff, FullLogDiff, ProcessedLogDiff

# Re-export enums
from vibenix.packaging_flow.model_prompts.enums import RefinementExit, PackagingFailure

# Standard search functions for all prompts that need them
SEARCH_FUNCTIONS = [
    search_nixpkgs_for_package_semantic,
    # search_nixpkgs_for_package_literal,
    # search_nix_functions,
    # search_nixpkgs_for_file,
    search_nixpkgs_manual_documentation,
]
EDIT_FUNCTIONS = [replace, insert_line_after, read_file]
SEARCH_AND_EDIT_FUNCTIONS = SEARCH_FUNCTIONS + EDIT_FUNCTIONS

ask_model_prompt = model_prompt_manager.ask_model_prompt

def run_formatter_after(func):
    """Decorator to automatically run Nix formatter after prompts that modify code."""
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            from vibenix.nix import run_formatter
            run_formatter()
            print("🎨 Code automatically formatted after model response")
        except Exception as e:
            print(f"⚠️  Warning: Failed to format code: {e}")
        return result
    return wrapper

@ask_model_prompt('pick_template.md')
def pick_template(project_page: str) -> TemplateType:
    """Select the appropriate template for a project."""
    ...


@ask_model_prompt('summarize_project.md')
def summarize_github(project_page: str) -> str:
    """Summarize a GitHub project page."""
    ...


@ask_model_prompt('refinement/evaluate_code.md')
def evaluate_code(code: str, previous_code: str, feedback: str) -> RefinementExit:
    """Evaluate whether refinement feedback has been successfully implemented."""
    ...


@ask_model_prompt('refinement/get_feedback.md', functions=SEARCH_FUNCTIONS)
def get_feedback(
    code: str,
    project_page: Optional[str] = None,
    iteration: int = 0,
    max_iterations: int = 0,
    additional_functions: List = []
) -> str:
    """Get feedback on a successfully built package."""
    ...


@run_formatter_after
@ask_model_prompt('refinement/refine_code.md', functions=SEARCH_AND_EDIT_FUNCTIONS)
def refine_code(
    code: str,
    feedback: str,
    project_page: Optional[str] = None,
    template_notes: Optional[str] = None,
    additional_functions: List = []
) -> str:
    """Refine a nix package based on feedback."""
    ...


@run_formatter_after
@ask_model_prompt('error_fixing/fix_build_error.md', functions=SEARCH_AND_EDIT_FUNCTIONS)
def fix_build_error(
    code: str,
    error: str,
    project_page: Optional[str] = None,
    template_notes: Optional[str] = None,
    additional_functions: List = [],
    is_broken_log_output: bool = False,
    is_dependency_build_error: bool = False,
    is_syntax_error: bool = False,
    attempted_tool_calls: List = [],
    tool_call_collector: List = None
) -> str:
    """Fix a build error in Nix code."""
    ...


@ask_model_prompt('error_fixing/fix_hash_mismatch.md', functions=EDIT_FUNCTIONS)
def fix_hash_mismatch(code: str, error: str) -> str:
    """Fix hash mismatch errors in Nix code."""
    ...


def evaluate_progress(log_diff: LogDiff) -> NixBuildErrorDiff:
    """Evaluate if the build made progress by comparing logs."""
    if isinstance(log_diff, FullLogDiff):
        # Use the full log template for complete logs
        @ask_model_prompt('progress_evaluation/evaluate_full_logs.md')
        def _evaluate_full(
            previous_log: str,
            new_log: str,
            initial_lines: int,
            improvement_lines: int
        ) -> NixBuildErrorDiff:
            ...
        return _evaluate_full(
            previous_log=log_diff.previous_log,
            new_log=log_diff.new_log,
            initial_lines=log_diff.initial_lines,
            improvement_lines=log_diff.improvement_lines
        )
    else:  # ProcessedLogDiff
        # Use the truncated log template for processed logs
        @ask_model_prompt('progress_evaluation/evaluate_truncated_logs.md')
        def _evaluate_truncated(
            previous_log_truncated: str,
            new_log_truncated: str,
            initial_lines: int,
            improvement_lines: int,
            divergence_line: int
        ) -> NixBuildErrorDiff:
            ...
        return _evaluate_truncated(
            previous_log_truncated=log_diff.previous_log_truncated,
            new_log_truncated=log_diff.new_log_truncated,
            initial_lines=log_diff.initial_lines,
            improvement_lines=log_diff.improvement_lines,
            divergence_line=log_diff.divergence_line
        )


@ask_model_prompt('failure_analysis/classify_packaging_failure.md', functions=SEARCH_FUNCTIONS)
def classify_packaging_failure(details: str) -> PackagingFailure:
    """Classify a packaging failure based on the provided details."""
    ...


@ask_model_prompt('failure_analysis/analyze_packaging_failure.md', functions=SEARCH_FUNCTIONS)
def analyze_package_failure(
    code: str,
    error: str,
    project_page: Optional[str] = None,
    template_notes: Optional[str] = None,
    additional_functions: List = []
) -> str:
    """Analyze why packaging failed."""
    ...


@ask_model_prompt('summarize_build.md', functions=[])
def summarize_build(
    summary: Optional[str] = None,
    additional_functions: List = []) -> str:
    """Summarize the build process and identify relations between the components."""
    ...


@ask_model_prompt('choose_builders.md', functions=[])
def choose_builders(
    available_builders: List[str],
    project_page: Optional[str] = None,
    additional_functions: List = []) -> List[str]:
    """Identify the Nix builder to use for packaging the project."""
    ...


@run_formatter_after
@ask_model_prompt('compare_template_builders.md', functions=SEARCH_AND_EDIT_FUNCTIONS)
def compare_template_builders(
    initial_code: str,
    builder_combinations_info: str,
    project_page: Optional[str] = None,
    additional_functions: List = []) -> str:
    """Compare the template builders with ones from choose_builders."""
    ...

# Import logger callbacks - use the global instance
