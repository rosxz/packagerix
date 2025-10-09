"""String replacement tool for modifying the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents
from difflib import unified_diff


@log_function_call("str_replace")
def str_replace(old_str: str, new_str: str) -> str:
    """
    Replace text in the current packaging expression. In case of ambiguous matches, select a bit more to ensure specificity.
    
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
        if old_str not in current_content:
            error_msg = f"Text to replace not found in packaging expression: '{old_str}'.\n Current packaging expression:\n{current_content}\n"
            ccl_logger.write_kv("error", error_msg)
            ccl_logger.leave_attribute(log_end=True)
            return error_msg
        
        # Perform replacement
        updated_content = current_content.replace(old_str, new_str)
        
        # Check if replacement actually changed something
        if updated_content == current_content:
            error_msg = "Replacement resulted in no changes"
            ccl_logger.write_kv("error", error_msg)
            ccl_logger.leave_attribute(log_end=True)
            return error_msg
        
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
        return "String replacement successful. Diff:\n" + diff
        
    except Exception as e:
        error_msg = f"Error during string replacement: {str(e)}"
        ccl_logger.write_kv("error", error_msg)
        ccl_logger.leave_attribute(log_end=True)
        return error_msg
