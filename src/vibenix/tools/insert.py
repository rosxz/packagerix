"""Insert tool to insert text at a specific location in the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents
from difflib import unified_diff


@log_function_call("insert")
def insert(insert_line: int, new_str: str) -> str:
    """Insert text at a specific location in the current packaging expression.
    Do not include or consider line number prefixes e.g. "1: ".
    
    Args:
        insert_line: The line number after which to insert the text (0 for beginning of file)
        new_str: The text to insert
    """
    print(f"📞 Function called: insert")
    return _insert(insert_line, new_str)


def _insert(insert_line: int, new_str: str) -> str:
    """Insert text at a specific location in the current packaging expression."""
    ccl_logger = get_logger()
    ccl_logger.enter_attribute("insert", log_start=True)
    
    try:
        # Get current package contents
        current_content = get_package_contents()
        previous_content = current_content  # Store previous content for comparison
        
        # Check if insert_line is valid
        lines = current_content.splitlines()
        if insert_line < 0 or insert_line > len(lines):
            error_msg = f"Invalid `insert_line`: {insert_line}. Currently, must be between 0 and {len(lines)}."
            ccl_logger.write_kv("error", error_msg)
            ccl_logger.leave_attribute(log_end=True)
            return error_msg
        
        # Insert the new string at the specified line
        lines.insert(insert_line, new_str)
        updated_content = "\n".join(lines)
        
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
        return "Successfuly inserted text. Diff:\n```{diff}```".format(diff=diff)
        
    except Exception as e:
        error_msg = f"Error inserting text: {str(e)}"
        ccl_logger.write_kv("error", error_msg)
        ccl_logger.leave_attribute(log_end=True)
        return error_msg
