"""String replacement tool for modifying the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents
from difflib import unified_diff


@log_function_call("str_replace")
def str_replace(old_str: str, new_str: str) -> str:
    """
    Replace text in the current packaging expression. Will only work if there's exactly one match for `old_str`.
    Do not include or consider line number prefixes e.g. "1: ".
    
    Args:
        old_str: The text to find and replace
        new_str: The replacement text
    """
    print(f"📞 Function called: str_replace")
    return _str_replace(old_str, new_str)


def _str_replace(old_str: str, new_str: str) -> str:
    """Replace text in the current packaging expression."""
    ccl_logger = get_logger()
    ccl_logger.enter_attribute("str_replace", log_start=True)
    
    try:
        # Get current package contents
        current_content = get_package_contents()
        previous_content = current_content  # Store previous content for comparison
        
        # Check if old_str exists in content
        count = current_content.count(old_str)
        if count == 0:
            error_msg = f"Error: `old_str` not found in packaging expression.\nTry replacing a smaller section of text, or analyzing the packaging code again with the `view` tool.\n"
            ccl_logger.write_kv("error", error_msg)
            ccl_logger.leave_attribute(log_end=True)
            return error_msg
        if count > 1:
            error_msg = f"Error: `old_str` is ambiguous and found {count} times in packaging expression.\n"
            ccl_logger.write_kv("error", error_msg)
            ccl_logger.leave_attribute(log_end=True)
            return error_msg
        
        # Perform replacement
        updated_content = current_content.replace(old_str, new_str)
        
        # Update the flake with new content
        update_flake(updated_content)
        
        # Get Diff between previous and updated content (with line numbers)
        diff = "\n".join(unified_diff(
            previous_content.splitlines(), 
            updated_content.splitlines(), 
            fromfile='before', 
            tofile='after', 
            lineterm=''
        ))
        ccl_logger.leave_attribute(log_end=True)
        from vibenix.tools.view import _view
        return f"Successfully replaced text. Diff:```\n{diff}```\n"
        
    except Exception as e:
        error_msg = f"Error during string replacement: {str(e)}"
        ccl_logger.write_kv("error", error_msg)
        ccl_logger.leave_attribute(log_end=True)
        return error_msg
