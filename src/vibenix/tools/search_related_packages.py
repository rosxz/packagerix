"""Search for related packages in nixpkgs and other related methods."""

import os
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from abc import ABC, abstractmethod
from typing import List, Set, Dict, Any
from vibenix.template.template_types import TemplateType
from vibenix.ccl_log import get_logger, log_function_call


def get_nixpkgs_source_path() -> str:
    """Get the nixpkgs source path from the template flake."""
    from vibenix import config
    import subprocess
    try:
        result = subprocess.run(
            ["nix", "build", ".#nixpkgs-src", "--no-link", "--print-out-paths"],
            cwd=config.template_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get nixpkgs source path: {e}")


@log_function_call("find_builder_functions")
def find_builder_functions(langs: List[str]) -> List[str]:
    """Find all builder functions in nixpkgs using regex patterns.

    Args:
        langs: List of language sets to consider (e.g., ['python', 'ruby', 'go'])
    Returns:
        A sorted list of unique builder functions found in nixpkgs"""
    return _find_builders_functions(langs)

def _find_builders_functions(langs: List[str]) -> List[str]:
    """Find all builder functions in nixpkgs using regex patterns.

    Returns:
        A sorted list of unique builder functions found in nixpkgs
        
    Raises:
        RuntimeError: If nixpkgs source path cannot be determined or search fails
    """
    print("📞 Function called: find_builder_functions")
    
    # Check for cached results first
    import json
    from pathlib import Path
    
    cache_dir = Path("cachedir")
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / "builder_functions.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            print("📋 Loading builder functions from cache")
            return cached_data['functions']
        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️ Cache file corrupted, regenerating: {e}")
    try:
        nixpkgs_path = get_nixpkgs_source_path()
    except Exception as e:
        raise RuntimeError(f"Failed to get nixpkgs source path: {e}")
    
    try:
        import subprocess

        additional_functions = [ # Not caught by the patterns below
            # appimageTools.wrapType2 # TODO
            'buildComposerProject2'
        ]
        blacklist_functions = [ # To remove from results
            'mkPulumiPackage', # TODO ???
            'mkChromiumDerivation', # very specific and actual name is mkDerivation under chromium set
            'buildZipPackage', # would require ...
            'buildNodePackage', # Would require a node2nix or nodeEnv ????? IDK
            'buildNodeShell',
            'buildMaubotPlugin', # Too specific
            'buildAzureCliPackage', # whatever
            'mkFranzDerivation', # whatever
            'mkWmApplication', #??
            'mkAppleDerivation',
            'mkMesonDerivation',
            'mkToolModule',
            'mkAliasDerivation',
            'mkAliasOptionModule',
            'mkChangedOptionModule',
            'mkLocalDerivation',
            'mkMergedOptionModule',
            'mkRemovedOptionModule',
            'mkRenamedOptionModule',
        ]
        # Hardcoded mappings
        helper = { "rust":  "rustPlatform", "dprint": "dprint-plugins", "open": "openmodelica",
                   "derivation": "stdenv", "shell": "stdenv" }
        
        # Generate regex patterns automatically
        prefixes = ['build', 'mk']
        suffixes = ['Package', 'Application', 'Module', 'Plugin', 'Derivation', 'Shell']
        
        patterns = []
        for prefix in prefixes:
            for suffix in suffixes:
                patterns.append(rf'\b{prefix}[A-Za-z]+{suffix}\b')
        
        # Use ripgrep for performance - search all .nix files
        # Use a dictionary to track which files each function appears in
        function_files = {}
        
        for pattern in patterns:
            # Use ripgrep to find matches across all .nix files - include filenames
            cmd = [
                'rg', 
                '--type', 'nix',           # Only search .nix files
                '--only-matching',         # Only show the matched part
                '--with-filename',         # Show filenames
                '--no-line-number',        # Don't show line numbers
                pattern,
                nixpkgs_path
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30  # 30 second timeout for performance
                )
                
                if result.returncode == 0:
                    # Track which files each function appears in
                    matches = result.stdout.strip().split('\n')
                    for match in matches:
                        if match.strip() and ':' in match:  # Skip empty lines and ensure format
                            filename, function_name = match.split(':', 1)
                            function_name = function_name.strip()
                            if function_name not in function_files:
                                function_files[function_name] = set()
                            function_files[function_name].add(filename)
                            
            except subprocess.TimeoutExpired:
                print(f"Warning: Search timed out for pattern {pattern}")
                continue
            except subprocess.CalledProcessError:
                # Pattern might not match anything, continue with next pattern
                continue
        
        # Filter functions that appear in more than one file and apply blacklist
        filtered_functions = []
        for func, files in function_files.items():
            if len(files) > 1 and func not in blacklist_functions:
                filtered_functions.append(func)
        # Add additional patterns (always include these)
        filtered_functions.extend(additional_functions)
        
        # Find qualified paths for the functions
        qualified_functions = []
        for func in filtered_functions:
            qualified_path = _find_qualified_path(func, helper, langs, nixpkgs_path)
            qualified_functions.append(qualified_path)
        
        # Sort results for consistent output
        sorted_functions = sorted(qualified_functions)
        
        # Cache the results
        try:
            cache_data = {
                'functions': sorted_functions,
                'timestamp': __import__('time').time(),
                'nixpkgs_path': nixpkgs_path
            }
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            print(f"💾 Cached {len(sorted_functions)} builder functions")
        except Exception as e:
            print(f"⚠️ Failed to cache results: {e}")
        
        if sorted_functions:
            return sorted_functions
        else:
            return None
            
    except FileNotFoundError:
        raise RuntimeError("ripgrep (rg) not found. Please ensure ripgrep is installed.")
    except Exception as e:
        raise RuntimeError(f"Error searching for builder functions: {str(e)}")


def _find_qualified_path(function_name: str, helper_map: dict, langs: List[str], nixpkgs_path: str) -> str:
    """
    Attempt to find the fully qualified path of a builder function in nixpkgs.
    Uses the lang_map to determine the language set if available.

    Args:
        function_name: The builder function name (e.g., buildPythonPackage)
        lang_map: Hardcoded language mapping for special cases
        nixpkgs_path: Path to the nixpkgs source
    Returns:

    """
    import re

    # Extract first capitalized segment
    match = re.search(r'[A-Z][a-z0-9]*', function_name)
    if not match:
        print(f"Could not extract language from function name: '{function_name}'")
        return None
    l = match.group().lower()
    if l in helper_map:
        l = helper_map[l]

    import subprocess
    for lang in [l] + langs: # even if the lang guessing fails, try all langs
        # Try different qualified path patterns
        test_paths = [
            f'pkgs',                  # pkgs.buildGoModule ( DONE BELOW )
            f'pkgs.{lang}Packages',     # pkgs.pythonPackages.buildPythonPackage
            f'pkgs.{lang}',             # pkgs.crystal.buildCrystalPackage
            f'pkgs.{lang}Utils',        # pkgs.kakouneUtils.buildKakounePlugin
            f'pkgs.{lang}Plugins',      # pkgs.?
        ]
        
        cmd = [
            'nix',
            'eval',
            '--impure',
            '--expr',
            f"let pkgs = import <nixpkgs> {{}}; candidates = [{" ".join(f"{{name=\"{path}\"; set=(let r = builtins.tryEval ({path}{" or null" if path != "pkgs" else ""}); in if r.success then r.value else null);}}" for path in test_paths)}]; found = builtins.filter (c: c.set != null && c.set ? {function_name}) candidates; in if found != [] then (builtins.head found).name else false"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.returncode == 0 and result.stdout.strip() != 'false':
                print(f"Found qualified path: {result.stdout.strip()}.{function_name}")
                return f"{result.stdout.strip().strip('"')}.{function_name}"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            continue # Try next path/lang
    return None


@log_function_call("find_builder_functions")
def get_builder_combinations(chosen_builders: List[str], keyword: str = None) -> str:
    return _get_builder_combinations(chosen_builders, keyword)

def _get_builder_combinations(chosen_builders: List[str], keyword: str = None) -> str:
    """
    Analyze nixpkgs for builder function usage patterns.
    
    Args:
        chosen_builders: List of builder functions to search for (in their fully qualified form)
        keyword: Optional keyword to filter results by file content
        
    Returns:
        A formatted string showing builder combination analysis
        
    Raises:
        RuntimeError: If nixpkgs source path cannot be determined or search fails
    """
    print(f"📞 Function called: analyze_builder_usage_patterns with builders: {chosen_builders}")
    
    ccl_logger = get_logger()
    ccl_logger.enter_attribute("get_builder_combinations", log_start=True)
    try:
        nixpkgs_path = get_nixpkgs_source_path()
    except Exception as e:
        raise RuntimeError(f"Failed to get nixpkgs source path: {e}")
    
    # Ensure mkDerivation is included
    all_builders = list(set(chosen_builders)) #  + ["pkgs.stdenv.mkDerivation"]
    ccl_logger.write_kv("chosen_builders", str(all_builders))
    
    print(f"Analyzing nixpkgs for builder usage: {all_builders}")
    
    # Data structures
    from collections import defaultdict
    package_to_builders = defaultdict(set)
    builder_to_packages = defaultdict(set)
    
    import subprocess
    from pathlib import Path
    # Search for each builder function in .nix files
    for builder in all_builders:
        print(f"Searching for {builder}...")
        function_name = builder.split('.')[-1]  # e.g., mkDerivation
        # TODO consider searching for the rest of the qualified path too?
        
        try:
            
            if keyword:
                cmd = [
                    "bash", "-c",
                    f"rg --type nix --files-with-matches '\\b{function_name}\\b' '{nixpkgs_path}' | xargs -r -I {{}} rg -l '\\b{keyword}\\b' '{{}}'"
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )
            else:
                result = subprocess.run([
                    "rg",
                    "--type", "nix",
                    "--files-with-matches",
                    rf"\b{function_name}\b",
                    nixpkgs_path
                ], capture_output=True, text=True, check=True)
            
            files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            for file_path in files:
                # Convert to relative path from nixpkgs
                rel_path = str(Path(file_path).relative_to(nixpkgs_path))
                package_to_builders[rel_path].add(builder)
                builder_to_packages[builder].add(rel_path)
                
        except subprocess.CalledProcessError as e:
            print(f"Error searching for {builder}: {e}")
            continue
    
    # Generate combinations and their frequencies
    combination_counts = defaultdict(set)
    
    for package, builders in package_to_builders.items():
        if len(builders) > 0:
            # Create a sorted combination name for consistency
            combination_name = " + ".join(sorted(builders))
            combination_counts[combination_name].add(package)
    
    # Sort combinations by frequency (descending)
    sorted_combinations = sorted(
        combination_counts.items(),
        key=lambda x: len(x[1]),
        reverse=True # Descending order
    )
    
    # Format results
    result_lines = []
    result_lines.append("="*80)
    result_lines.append("BUILDER COMBINATION ANALYSIS")
    result_lines.append("="*80)
    
    ccl_logger.enter_attribute("results")
    iter = 0
    for combination, packages in sorted_combinations:
        ccl_logger.log_iteration_start(iter)
        ccl_logger.write_kv("combination", combination)
        result_lines.append(f"\n{combination} ({len(packages)} packages):")
        result_lines.append("-" * (len(combination) + 20))
        
        # Randomize package order and limit to first 20 for readability
        import random
        randomized_packages = list(packages)
        PACKAGE_LIMIT = 10
        random.shuffle(randomized_packages)
        result_lines.extend([f"  {package}" for package in randomized_packages[:10]])
        ccl_logger.write_kv("packages", str(randomized_packages[:10]))
        
        if len(randomized_packages) > PACKAGE_LIMIT:
            result_lines.append(f"  ... and {len(randomized_packages) - PACKAGE_LIMIT} more packages")
        ccl_logger.write_kv("package_count", str(len(packages)))
        iter += 1
    ccl_logger.leave_list()
    ccl_logger.leave_attribute()
    ccl_logger.leave_attribute(log_end=True)
    
    return "\n".join(result_lines)
