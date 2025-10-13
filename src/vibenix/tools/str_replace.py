"""String replacement tool for modifying the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import update_flake, get_package_contents


@log_function_call("str_replace")
def str_replace(old_str: str, new_str: str, collision: int = None) -> str:
    """
    Replace text in the current packaging expression (only a single text match).
    Do not include or consider line number prefixes e.g. "1: ".
    
    Args:
        old_str: The text to find and replace
        new_str: The replacement text
        collision: If `old_str` is not unique, specify which occurrence to replace (1-based index)
    """
    print(f"📞 Function called: str_replace")
    return _str_replace(old_str, new_str, collision)


def _str_replace(old_str: str, new_str: str, collision: int = None) -> str:
    """Replace text in the current packaging expression."""
    
    try:
        # Get current package contents
        current_content = get_package_contents()
        previous_content = current_content  # Store previous content for comparison
        
        # Check if old_str exists in content
        count = current_content.count(old_str)
        if count == 0:
            error_msg = f"Error: `old_str` not found in packaging expression.\n"
            return error_msg
        if count > 1:
            if not collision or collision < 1 or collision > count:
                error_msg = f"Error: `old_str` is ambiguous and found {count} times in packaging expression.\n"
                error_msg += f"Matches in lines:\n"
                for i, line in enumerate(current_content.splitlines(), start=1):
                    if old_str in line:
                        error_msg += f"{i}: {line}\n"
                return error_msg
            else:
                # Replace only the specified occurrence
                parts = current_content.split(old_str)
                current_content = old_str.join(parts[:collision]) + new_str + old_str.join(parts[collision:])
                updated_content = current_content
                update_flake(updated_content)
                
                # Show updated code starting from first changed line
                previous_lines = previous_content.splitlines()
                updated_lines = updated_content.splitlines()
                first_diff_index = next(i for i in range(min(len(previous_lines), len(updated_lines))) if previous_lines[i] != updated_lines[i])
                diff = "\n".join([f"{i+1}: {line}" for i, line in enumerate(updated_lines[first_diff_index:], start=first_diff_index)])
                return_msg = f"Lines starting from {first_diff_index + 1}:\n```\n{diff}\n```"
                
                return f"Successfully replaced text. {return_msg}"
        
        # Perform replacement
        updated_content = current_content.replace(old_str, new_str)
        
        # Update the flake with new content
        update_flake(updated_content)
        
        # Show updated code, logic: 1) if line count stays the same, show only changed lines; 2) if line count changes, show all lines starting from first changed line
        previous_lines = previous_content.splitlines()
        updated_lines = updated_content.splitlines()
        return_msg = None
        if len(previous_lines) == len(updated_lines):
            diff_lines = [f"{i+1}: {updated_lines[i]}" for i in range(len(updated_lines)) if previous_lines[i] != updated_lines[i]]
            diff = "\n".join(diff_lines)
            return_msg = f"Updated lines:\n```\n{diff}\n```"
        else:
            first_diff_index = next(i for i in range(min(len(previous_lines), len(updated_lines))) if previous_lines[i] != updated_lines[i])
            diff = "\n".join([f"{i+1}: {line}" for i, line in enumerate(updated_lines[first_diff_index:], start=first_diff_index)])
            return_msg = f"Lines starting from {first_diff_index + 1}:\n```\n{diff}\n```"

        return f"Successfully replaced text. {return_msg}"
        
    except Exception as e:
        error_msg = f"Error during string replacement: {str(e)}"
        return error_msg
