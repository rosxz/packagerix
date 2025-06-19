import subprocess
import requests
import json

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
    
