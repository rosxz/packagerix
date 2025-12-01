"""Pagination for error messages."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents


@log_function_call("error_pagination")
def error_pagination(page: int) -> str:
    """Paginate error messages to show a specific page."""
    print(f"📞 Function called: error_pagination with page={page}")
    return _error_pagination(page)


def _error_pagination(page: int) -> str:
    """Paginate error messages to show a specific page."""
    
    try:
        from vibenix import config
        if config.solution_stack is None or len(config.solution_stack) == 0:
            return "No errors available to paginate through."
        result = config.solution_stack[-1].result
        if result.success or result.error is None:
            return "No errors available to paginate through."
        error = result.error
        return error.truncated(page=page)
        
    except Exception as e:
        return f"Error during error pagination: {e}"
