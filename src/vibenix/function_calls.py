import subprocess
import requests
import json
import os
from vibenix.ccl_log import get_logger
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pickle
from pathlib import Path

def search_nixpkgs_for_package_literal(query: str) -> str:
    """Search the nixpkgs repository of Nix code for the given package using fuzzy search.
    
    Returns a concise summary of matching packages, using fzf for fuzzy matching
    and distinguishing between matches in package set names vs package names within sets.
    """

    print("📞 Function called: search_nixpkgs_for_package_literal with query: ", query)
    get_logger().log_function_call("search_nixpkgs_for_package_literal", query=query)
    
    # Get all packages (using ^ to match everything)
    nix_result = subprocess.run(
        ["nix", "search", "--json", "nixpkgs", "^"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    if nix_result.returncode != 0 or not nix_result.stdout.strip():
        return f"Failed to fetch package list from nixpkgs"
    
    # Convert JSON to lines with format: package_name|json_entry
    # This makes it easier to parse after fzf
    jq_filter = r'''
    to_entries 
    | map(
        (.key |= sub("legacyPackages\\.x86_64-linux\\."; ""))
        | "\(.key)|\(.value | @json)"
      )
    | .[]
    '''
    
    jq_result = subprocess.run(
        ["jq", "-r", jq_filter],
        input=nix_result.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    if jq_result.returncode != 0:
        return f"Failed to process package list: {jq_result.stderr}"
    
    # Use fzf for fuzzy search
    # --with-nth=1 tells fzf to only search on the first field (package name)
    fzf_result = subprocess.run(
        ["fzf", f"--filter={query}", "-i", "--delimiter=|", "--with-nth=1"],
        input=jq_result.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Parse fzf results
    fuzzy_matches = []
    if fzf_result.returncode == 0 and fzf_result.stdout.strip():
        for line in fzf_result.stdout.strip().split('\n')[:200]:  # Limit to top 200 matches
            if not line or '|' not in line:
                continue
            try:
                pkg_name, json_str = line.split('|', 1)
                pkg_info = json.loads(json_str)
                fuzzy_matches.append({
                    'name': pkg_name,
                    'version': pkg_info.get('version', ''),
                    'description': pkg_info.get('description', ''),
                })
            except (json.JSONDecodeError, ValueError):
                continue
    
    # If fuzzy search returns few results, also do substring matching
    substring_matches = []
    if len(fuzzy_matches) < 20:
        query_lower = query.lower()
        for line in jq_result.stdout.strip().split('\n'):
            if not line or '|' not in line:
                continue
            try:
                pkg_name, json_str = line.split('|', 1)
                if query_lower in pkg_name.lower():
                    # Check if already in fuzzy matches
                    if not any(m['name'] == pkg_name for m in fuzzy_matches):
                        pkg_info = json.loads(json_str)
                        substring_matches.append({
                            'name': pkg_name,
                            'version': pkg_info.get('version', ''),
                            'description': pkg_info.get('description', ''),
                        })
                        if len(substring_matches) >= 50:  # Limit substring matches
                            break
            except (json.JSONDecodeError, ValueError):
                continue
    
    # Combine matches: fuzzy matches first, then substring matches
    matches = fuzzy_matches + substring_matches
    
    if not matches:
        return f"No packages found matching '{query}'"
    
    # Categorize results while preserving fzf's ranking
    package_sets = {}  # package_set -> list of packages
    individual_packages = []
    package_set_order = []  # Track order of first appearance
    
    for match in matches:
        pkg_name = match['name']
        if '.' in pkg_name:
            package_set = pkg_name.split('.', 1)[0]
            if package_set not in package_sets:
                package_sets[package_set] = []
                package_set_order.append(package_set)
            package_sets[package_set].append(match)
        else:
            individual_packages.append(match)
    
    # Build result as list to maintain order
    result_items = []
    
    # Add package sets (preserving fzf ranking order)
    for set_name in package_set_order[:10]:  # Show first 10 package sets by order of appearance
        packages = package_sets[set_name]
        count = len(packages)
        
        if count <= 3:
            # Show all packages if 3 or fewer
            for pkg in packages:
                result_items.append((pkg['name'], {
                    "description": pkg['description'],
                    "pname": pkg['name'].split('.')[-1],
                    "version": pkg['version']
                }))
        else:
            # Show first 3 as sample
            for pkg in packages[:3]:
                result_items.append((pkg['name'], {
                    "description": pkg['description'],
                    "pname": pkg['name'].split('.')[-1],
                    "version": pkg['version']
                }))
            # Add comment about more packages
            result_items.append((f"_comment_{set_name}", f"... and {count - 3} more packages in {set_name}"))
    
    # Add individual packages (max 5)
    for pkg in individual_packages[:5]:
        result_items.append((pkg['name'], {
            "description": pkg['description'],
            "pname": pkg['name'],
            "version": pkg['version']
        }))
    
    if len(individual_packages) > 5:
        result_items.append(("_comment_individual", f"... and {len(individual_packages) - 5} more individual packages"))
    
    # Manually build JSON with comments
    json_lines = ["{"]    
    for i, (key, value) in enumerate(result_items):
        if key.startswith("_comment_"):
            json_lines.append(f"  // {value}")
        else:
            json_str = json.dumps({key: value}, indent=2)[1:-1].strip()
            # Add comma if not last real item
            has_more = any(not k.startswith("_comment_") for k, _ in result_items[i+1:])
            if has_more:
                json_str += ","
            json_lines.append("  " + json_str)
    json_lines.append("}")
    
    return "\n".join(json_lines)

def search_nixpkgs_for_package_semantic(query: str) -> str:
    """Search the nixpkgs repository using semantic similarity with embeddings.
    
    Uses sentence transformers to find semantically similar package names and descriptions.
    """
    print("📞 Function called: search_nixpkgs_for_package_semantic (embeddings) with query: ", query)
    get_logger().log_function_call("search_nixpkgs_for_package_semantic", query=query)
    
    # Get path to pre-computed embeddings from environment
    embeddings_path = os.environ.get('NIXPKGS_EMBEDDINGS')
    if not embeddings_path:
        return "Error: NIXPKGS_EMBEDDINGS environment variable not set. Please run from nix develop shell."
    
    if not os.path.exists(embeddings_path):
        return f"Error: Pre-computed embeddings not found at {embeddings_path}"
    
    # Load pre-computed embeddings
    try:
        with open(embeddings_path, 'rb') as f:
            data = pickle.load(f)
            embeddings = data['embeddings']
            package_names = data['names']
            packages = data['packages']
    except Exception as e:
        return f"Error loading pre-computed embeddings: {str(e)}"
    
    # Load model for encoding the query
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Encode query and find similar packages
    query_embedding = model.encode([query])
    similarities = cosine_similarity(query_embedding, embeddings)[0]
    
    # Get top 200 results
    top_indices = np.argsort(similarities)[::-1][:200]
    
    # Build matches list
    matches = []
    # Create package dict from pre-computed data
    package_dict = {entry['key']: entry['value'] for entry in packages}
    
    for idx in top_indices:
        if similarities[idx] < 0.2:  # Skip very low similarity scores
            break
        pkg_name = package_names[idx]
        pkg_info = package_dict.get(pkg_name, {})
        matches.append({
            'name': pkg_name,
            'version': pkg_info.get('version', ''),
            'description': pkg_info.get('description', ''),
            'score': similarities[idx]
        })
    
    if not matches:
        return f"No packages found matching '{query}'"
    
    # Categorize results
    package_sets = {}
    individual_packages = []
    package_set_order = []
    
    for match in matches:
        pkg_name = match['name']
        if '.' in pkg_name:
            package_set = pkg_name.split('.', 1)[0]
            if package_set not in package_sets:
                package_sets[package_set] = []
                package_set_order.append(package_set)
            package_sets[package_set].append(match)
        else:
            individual_packages.append(match)
    
    # Build result as list to maintain order
    result_items = []
    
    # Add package sets
    for set_name in package_set_order[:10]:
        packages = package_sets[set_name]
        count = len(packages)
        
        if count <= 3:
            for pkg in packages:
                result_items.append((pkg['name'], {
                    "description": pkg['description'],
                    "pname": pkg['name'].split('.')[-1],
                    "version": pkg['version']
                }))
        else:
            for pkg in packages[:3]:
                result_items.append((pkg['name'], {
                    "description": pkg['description'],
                    "pname": pkg['name'].split('.')[-1],
                    "version": pkg['version']
                }))
            # Add comment about more packages
            result_items.append((f"_comment_{set_name}", f"... and {count - 3} more packages in {set_name}"))
    
    # Add individual packages
    for pkg in individual_packages[:5]:
        result_items.append((pkg['name'], {
            "description": pkg['description'],
            "pname": pkg['name'],
            "version": pkg['version']
        }))
    
    if len(individual_packages) > 5:
        result_items.append(("_comment_individual", f"... and {len(individual_packages) - 5} more individual packages"))
    
    # Manually build JSON with comments
    json_lines = ["{"]    
    for i, (key, value) in enumerate(result_items):
        if key.startswith("_comment_"):
            json_lines.append(f"  // {value}")
        else:
            json_str = json.dumps({key: value}, indent=2)[1:-1].strip()
            # Add comma if not last real item
            has_more = any(not k.startswith("_comment_") for k, _ in result_items[i+1:])
            if has_more:
                json_str += ","
            json_lines.append("  " + json_str)
    json_lines.append("}")

    return "\n".join(json_lines)

def search_nix_functions(query: str) -> str:
    """
    Search for Nix builtin and library functions by name.
    Can be used to search for package sets or packages by their full name, or a part of their name.
    Invoke multiple times to find different spellings, because search is not fuzzy.
    """
    
    print("📞 Function called: search_nix_functions with query: ", query)
    get_logger().log_function_call("search_nix_functions", query=query)
    
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
            return f"No Nix functions found matching '{query}'"
            
    except FileNotFoundError:
        return "Error: fzf not found. Please ensure fzf is available in the environment."
    except Exception as e:
        return f"Error searching Nix functions: {str(e)}"
    
