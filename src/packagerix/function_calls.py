import subprocess
import requests
import json
import os

def search_nixpkgs_for_package(query: str) -> str:
    """Search the nixpkgs repository of Nix code for the given package"""

    print("📞 Function called: search_nixpkgs_for_package with query: ", query)
    
    # Use shell=True to run the piped command with jq
    # TODO: fix platform dependence here for mac support support
    cmd = f'nix search --json nixpkgs {query} | jq "with_entries(.key |= sub(\\"legacyPackages\\\\.x86_64-linux\\\\.\\"; \\"\\"))"'
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    
    if result.returncode == 0 and result.stdout.strip():
        print("Result: ", result.stdout)
        return result.stdout
    else:
        return f"no results found for query '{query}'"


def web_search(query: str) -> str:
    """Perform a web search with a query"""
    
    print("📞 Function called: web_search with query: ", query)
    try:
        result = subprocess.run(["ddgr", "--json", query], text=True, capture_output=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        else:
            return f"no search results found for query '{query}'"
    except subprocess.TimeoutExpired:
        return "search timed out"
    except FileNotFoundError:
        return "search tool not found, please install ddgr"
    

def fetch_url_content(url: str) -> str:
    """Fetch HTML content from a URL"""
    
    print("📞 Function called: fetch_url_content with url: ", url)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        return f"Error fetching URL: {str(e)}"

def search_nix_functions(query: str) -> str:
    """Search for Nix builtin and library functions by name"""
    
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
            ["fzf", f"--filter={query}", "--exact"],
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
            return f"No Nix functions found matching '{query}'"
            
    except FileNotFoundError:
        return "Error: fzf not found. Please ensure fzf is available in the environment."
    except Exception as e:
        return f"Error searching Nix functions: {str(e)}"
    
