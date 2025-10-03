"""Search for Nix builtin and library functions."""

import os
import subprocess
from vibenix.ccl_log import get_logger, log_function_call
from vibenix.tools.search_nixpkgs_manual_documentation import search_keyword_in_documentation


@log_function_call("search_nix_functions")
def search_nix_functions(query: str) -> str:
    """
    Search for Nix builtin and library functions by name.
    Can be used to search for package sets or packages by their full name, or a part of their name.
    Invoke multiple times to find different spellings, because search is not fuzzy.
    """
    
    print("📞 Function called: search_nix_functions with query: ", query)
    
    try:
        # Get the path from environment variable
        function_names_path = os.environ.get('NOOGLE_FUNCTION_NAMES')
        
        if not function_names_path:
            raise RuntimeError("NOOGLE_FUNCTION_NAMES environment variable not set. Please run from nix develop shell.")
        
        if not os.path.exists(function_names_path):
            raise FileNotFoundError(f"Noogle function names file not found at {function_names_path}")
        
        # Use fzf to filter the function names
        result = subprocess.run(
            ["fzf", f"--filter={query}", "--exact", "-i"],
            stdin=open(function_names_path, 'r'),
            text=True,
            capture_output=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            matches = result.stdout.strip().split('\n')
            # Limit results to prevent overwhelming output
            limited_matches = matches[:50]
            result_text = "\n".join(limited_matches)
            if len(matches) > 50:
                result_text += f"\n\n... and {len(matches) - 50} more results"
            return result_text
        else:
            return f"No Nix functions found matching '{query}' from querying Noogle.\n" + search_keyword_in_documentation(query)
            
    except FileNotFoundError:
        return "Error: fzf not found. Please ensure fzf is available in the environment."
    except Exception as e:
        return f"Error searching Nix functions: {str(e)}"
