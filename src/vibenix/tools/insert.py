"""Insert tool to insert text at a specific location in the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents
from difflib import unified_diff


@log_function_call("insert")
def insert(insert_line: int, new_str: str) -> str:
    """Insert text at a specific line in the current packaging expression.
    Specify the line number **AFTER WHICH**, to insert the new text.
    
    Args:
        **insert_line: The line number after which to insert the text (0 for beginning of file)**
        new_str: The text to insert as a new line

    Example:
        # If file has lines: 
        1: line one
        2: line two
        # and you call:
        insert(1, "inserted line")
        # you get:
        1: line one
        2: inserted line
        3: line two
    """
    print(f"📞 Function called: insert")
    return _insert(insert_line, new_str)


def _insert(insert_line: int, new_str: str) -> str:
    """Insert text at a specific location in the current packaging expression."""
    
    try:
        # Get current package contents
        current_content = get_package_contents()
        new_str = new_str.rstrip("\n").lstrip("\n")  # Remove leading/trailing newlines
        
        # Check if insert_line is valid
        lines = current_content.splitlines()
        if insert_line < 0 or insert_line > len(lines):
            error_msg = f"Invalid `insert_line`: {insert_line}. Valid range is 0 to {len(lines)}." # TODO
            return error_msg
        
        # Insert the new string at the specified line
        lines.insert(insert_line, new_str)
        updated_content = "\n".join(lines)
        
        # Check if replacement actually changed something
        if updated_content == current_content:
            error_msg = "Replacement resulted in no changes"
            return error_msg

        # Test if it breaks syntax
        from vibenix.nix import check_syntax
        syntax_err = check_syntax(updated_content)
        if syntax_err and "expected" in syntax_err:
            syntax_error_index = syntax_err.index("error: syntax error")
            error_truncated = syntax_err[syntax_error_index:]
            error_msg = f"Error: Insertion aborted, breaks syntax:\n{error_truncated}"
            return error_msg
        
        # Update the flake with new content
        update_flake(updated_content)
        
        # Show all lines starting from first changed line
        start_line = insert_line-1
        updated_lines = updated_content.splitlines()
        diff = "\n".join([f"{i+1:>3}: {line}" for i, line in enumerate(updated_lines[start_line:], start=start_line)])
        return_msg = f"Lines starting from {insert_line}:\n```\n{diff}\n```"

        return f"Successfuly inserted text. {return_msg}"
        
    except Exception as e:
        error_msg = f"Error inserting text: {str(e)}"
        return error_msg
