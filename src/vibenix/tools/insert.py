"""Insert tool to insert text at a specific location in the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents
from difflib import unified_diff


@log_function_call("insert")
def insert(insert_line: int, new_str: str) -> str:
    """Insert text at a specific location in the current packaging expression.
    Do not include or consider line number prefixes e.g. "1: ".
    The `insert_line` is the line where new_str will be starting from (0 for beginning of file). Contents previously on that line, are pushed ahead.
    
    Args:
        insert_line: The line number after which to insert the text (0 for beginning of file)
        new_str: The text to insert
    """
    print(f"📞 Function called: insert")
    return _insert(insert_line, new_str)


def _insert(insert_line: int, new_str: str) -> str:
    """Insert text at a specific location in the current packaging expression."""
    
    try:
        # Get current package contents
        current_content = get_package_contents()
        previous_content = current_content  # Store previous content for comparison
        
        # Check if insert_line is valid
        lines = current_content.splitlines()
        if insert_line < 0 or insert_line >= len(lines):
            error_msg = f"Invalid `insert_line`: {insert_line}. Currently, there are {len(lines)-1} lines total (0-indexed, inclusive)."
            return error_msg
        
        # Insert the new string at the specified line
        lines.insert(insert_line, new_str)
        updated_content = "\n".join(lines)
        
        # Check if replacement actually changed something
        if updated_content == current_content:
            error_msg = "Replacement resulted in no changes"
            return error_msg
        
        # Update the flake with new content
        update_flake(updated_content)
        
        # Show all lines starting from first changed line
        start_line = insert_line
        updated_lines = updated_content.splitlines()
        diff = "\n".join([f"{i+1}: {line}" for i, line in enumerate(updated_lines[start_line:], start=start_line)])
        return_msg = f"Lines starting from {insert_line}:\n```\n{diff}\n```"

        return f"Successfuly inserted text. {return_msg}"
        
    except Exception as e:
        error_msg = f"Error inserting text: {str(e)}"
        return error_msg
