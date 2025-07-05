import subprocess
import requests
import json
import os
from vibenix.ccl_log import get_logger

def search_nixpkgs_for_package(query: str) -> str:
    """Search the nixpkgs repository of Nix code for the given package.
    
    Returns a concise summary of matching packages, distinguishing between
    matches in package set names vs package names within sets.
    """

    print("📞 Function called: search_nixpkgs_for_package with query: ", query)
    get_logger().log_function_call("search_nixpkgs_for_package", query=query)
    
    # Run nix search first, explicitly separate stdout and stderr
    nix_result = subprocess.run(
        ["nix", "search", "--json", "nixpkgs", query],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    if nix_result.returncode != 0 or not nix_result.stdout.strip():
        return f"no results found for query '{query}'"
    
    # Pipe to jq to remove the platform-specific prefix
    # TODO: fix platform dependence here for mac support
    jq_filter = r'with_entries(.key |= sub("legacyPackages\\.x86_64-linux\\."; ""))'
    jq_result = subprocess.run(
        ["jq", jq_filter],
        input=nix_result.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    if jq_result.returncode == 0 and jq_result.stdout.strip():
        try:
            # Parse the JSON results
            results = json.loads(jq_result.stdout)
            total_count = len(results)
            query_lower = query.lower()
            
            # Categorize results
            package_sets_with_matches = {}  # package_set -> list of matching packages
            package_set_name_matches = {}  # package_set -> total count (when set name matches)
            individual_packages = {}  # package_name -> package_info
            
            for pkg_name, pkg_info in results.items():
                if '.' in pkg_name:
                    parts = pkg_name.split('.', 1)
                    package_set = parts[0]
                    package_in_set = parts[1] if len(parts) > 1 else ""
                    
                    # Check if the match is in the package set name or the package name
                    if query_lower in package_set.lower():
                        # Match is in the package set name
                        if package_set not in package_set_name_matches:
                            package_set_name_matches[package_set] = 0
                        package_set_name_matches[package_set] += 1
                    else:
                        # Match must be in the package name within the set
                        if package_set not in package_sets_with_matches:
                            package_sets_with_matches[package_set] = []
                        package_sets_with_matches[package_set].append({
                            "name": pkg_name,
                            "version": pkg_info.get("version", ""),
                            "description": pkg_info.get("description", "")
                        })
                else:
                    individual_packages[pkg_name] = pkg_info
            
            # Build the result
            result_lines = [f"Found {total_count} packages matching '{query}'\n"]
            
            # Package sets where the SET NAME matches the query
            if package_set_name_matches:
                sorted_set_matches = sorted(package_set_name_matches.items(), 
                                          key=lambda x: x[1], reverse=True)[:10]
                result_lines.append("## Package sets matching by name:")
                for set_name, count in sorted_set_matches:
                    result_lines.append(f"  - {set_name}: {count} packages total")
                if len(package_set_name_matches) > 10:
                    result_lines.append(f"  ... and {len(package_set_name_matches) - 10} more sets")
                result_lines.append("")
            
            # Package sets where PACKAGES within match the query
            if package_sets_with_matches:
                result_lines.append("## Packages within sets:")
                sorted_sets = sorted(package_sets_with_matches.items(), 
                                   key=lambda x: len(x[1]), reverse=True)[:10]
                
                for set_name, packages in sorted_sets:
                    count = len(packages)
                    if count <= 3:
                        # Show all packages if 3 or fewer
                        result_lines.append(f"  {set_name}:")
                        for pkg in packages:
                            result_lines.append(f"    - {pkg['name']}: {pkg['description'][:60]}...")
                    else:
                        # Show first 3 as sample
                        result_lines.append(f"  {set_name}: ({count} matches)")
                        for pkg in packages[:3]:
                            result_lines.append(f"    - {pkg['name']}: {pkg['description'][:60]}...")
                        result_lines.append(f"    ... and {count - 3} more")
                    result_lines.append("")
            
            # Individual packages (max 5)
            if individual_packages:
                result_lines.append("## Individual packages:")
                for i, (pkg_name, pkg_info) in enumerate(list(individual_packages.items())[:5]):
                    desc = pkg_info.get("description", "")[:60]
                    version = pkg_info.get("version", "")
                    result_lines.append(f"  - {pkg_name} ({version}): {desc}...")
                
                if len(individual_packages) > 5:
                    result_lines.append(f"  ... and {len(individual_packages) - 5} more")
                result_lines.append("")
            
            # Add usage hints
            result_lines.append("## Tips:")
            result_lines.append("- Use partial matching: 'python3Packages.req' finds 'requests'")
            result_lines.append("- Be more specific: 'python3Packages.django' instead of just 'django'")
            result_lines.append("- Try variations: 'qt5', 'qt6', 'libsForQt5' for Qt packages")
            
            return "\n".join(result_lines)
            
        except json.JSONDecodeError:
            # If JSON parsing fails, return the original output
            return jq_result.stdout
    elif not jq_result.stdout.strip():
        return f"nixpkgs search returned no results for {query}"
    elif jq_result.returncode != 0:
        raise ValueError(f"jq failed with return code {jq_result.returncode}, stderr: {jq_result.stderr}")

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
    
