"""View tool to examine the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import get_package_contents


@log_function_call("view")
def view() -> str:
    """Examine the contents of the current packaging expression.

    Args:
        view_range: Optional(list[int]): A list of two integers specifying the start and end lines to view (0-indexed, inclusive).
    """
    print(f"📞 Function called: view")
    return _view(do_log=True)


def _view(view_range: list[int]=None, do_log: bool=False) -> str:
    """Examine the contents of the current packaging expression."""
    if do_log:
        ccl_logger = get_logger()
        ccl_logger.enter_attribute("view", log_start=True)
    
    try:
        # Get current package contents
        current_content = get_package_contents()
        
        # Check if view_range is valid
        lines = current_content.splitlines()
        # Add `<line_number>: ` prefix to each line
        lines = [f"{i:>3}: {line}" for i, line in enumerate(lines)]
        if view_range:
            if len(view_range) != 2:
                error_msg = "Invalid `view_range`: must be a list of two integers."
                if do_log:
                    ccl_logger.write_kv("error", error_msg)
                    ccl_logger.leave_attribute(log_end=True)
                return error_msg
            start, end = view_range
            # if its trying to view a single line, make end one more than start (just to make life easier for the model)
            if start == end:
                end += 1
            if start < 0 or end >= len(lines) or start >= end:
                error_msg = f"Invalid `view_range`: {view_range}. Packaging code has lines between 0 and {len(lines)-1} (0-indexed, inclusive), and start < end must hold."
                if do_log:
                    ccl_logger.write_kv("error", error_msg)
                    ccl_logger.leave_attribute(log_end=True)
                return error_msg
            # Slice the lines to the specified range
            lines = lines[start:end]

        # Join the lines back into a single string
        content_to_view = "\n".join(lines)
        if do_log:
            ccl_logger.write_kv("viewed_lines", f"{view_range if view_range else 'all'}")
            ccl_logger.leave_attribute(log_end=True)
        return content_to_view
        
    except Exception as e:
        error_msg = f"Error viewing package contents: {str(e)}"
        if do_log:
            ccl_logger.write_kv("error", error_msg)
            ccl_logger.leave_attribute(log_end=True)
        return error_msg
