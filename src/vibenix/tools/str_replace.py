"""String replacement tool for modifying the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents


@log_function_call("str_replace")
def str_replace(old_str: str, new_str: str, occurrence: int = 1) -> str:
    """
    Replace text in the current packaging expression.
    DO NOT include line numbers (`1: `), just the exact text to find and replace.
    
    Args:
        old_str: The exact text to find and replace (must match exactly including whitespace)
        new_str: The replacement text
        occurrence: Which occurrence to replace if multiple matches exist (1-based, defaults to first)
    
    Example:
        str_replace("buildInputs = [];", "buildInputs = [ cmake ];")
    """
    print(f"📞 Function called: str_replace")
    return _str_replace(old_str, new_str, occurrence)


def _str_replace(old_str: str, new_str: str, occurrence: int = 1) -> str:
    """Replace text in the current packaging expression."""
    
    try:
        # Get current package contents
        current_content = get_package_contents()
        previous_content = current_content
        
        # Check if old_str exists in content
        count = current_content.count(old_str)
        if count == 0:
            lines = current_content.splitlines()
            similar_lines = []
            for i, line in enumerate(lines, start=1):
                if old_str.strip() in line or any(word in line for word in old_str.split() if len(word) > 3):
                    similar_lines.append(f"{i:>3}: {line}")
            
            error_msg = f"Error: Text not found in packaging expression."#\n Looked for: {repr(old_str)}"
            #if similar_lines:
            #    error_msg += f"\n\nSimilar lines found:\n" + "\n".join(similar_lines[:5])
            return error_msg

        # Validate occurrence parameter
        if occurrence < 1:
            error_msg = f"Error: `occurrence` must be >= 1, got {occurrence}"
            return error_msg
            
        if occurrence > count:
            error_msg = f"Error: Requested occurrence {occurrence} but only found {count} matches.\n"
            error_msg += "All occurrences:\n"
            for i, line in enumerate(current_content.splitlines(), start=1):
                if old_str in line:
                    error_msg += f"{i:>3}: {line}\n"
            return error_msg
        
        # Replace the specified occurrence
        parts = current_content.split(old_str)
        if len(parts) >= occurrence + 1:
            updated_content = old_str.join(parts[:occurrence]) + new_str + old_str.join(parts[occurrence:])
        else:
            updated_content = current_content.replace(old_str, new_str)

        # Test if it breaks syntax
        #from vibenix.nix import check_syntax
        #syntax_err = check_syntax(updated_content)
        #if syntax_err and "attribute" not in syntax_err:
        #    syntax_error_index = syntax_err.index("error: syntax error")
        #    error_truncated = syntax_err[syntax_error_index:]
        #    error_msg = f"Error: Insertion aborted, breaks syntax:\n{error_truncated}"
        #    return error_msg

        update_flake(updated_content)
        
        # Show updated lines (and ones with changed line numbers)
        previous_lines = previous_content.splitlines()
        updated_lines = updated_content.splitlines()
        return_msg = None
        if len(previous_lines) == len(updated_lines):
            diff_lines = [f"{i:>3}: {updated_lines[i]}" for i in range(len(updated_lines)) if previous_lines[i] != updated_lines[i]]
            diff = "\n".join(diff_lines)
            return_msg = f"Updated lines:\n```\n{diff}\n```"
        else:
            # Updated lines get * marker, other lines are shown for context (updated line number)
            new_str_idx = updated_content.index(new_str)
            first_diff_index = updated_content[:new_str_idx].count("\n")
            diff_lines = []
            for i, line in enumerate(updated_lines[first_diff_index:], start=first_diff_index):
                if i < first_diff_index+len(new_str.splitlines()):
                    diff_lines += [f"*{i + 1:>3}: {line}"]
                else:
                    diff_lines += [f" {i + 1:>3}: {line}"]
            diff = "\n".join(diff_lines)
            return_msg = f"Showing lines starting from {first_diff_index + 1}:\n```\n{diff}\n```"

        return f"Successfully replaced text. {return_msg}"
        
    except Exception as e:
        error_msg = f"Error during string replacement: {str(e)}"
        return error_msg
