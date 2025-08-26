"""Search tools for nixpkgs manual documentation, specifically language and framework guides."""

import os
import subprocess
from pathlib import Path
from typing import List
from vibenix.ccl_log import get_logger, log_function_call


def get_nixpkgs_source_path() -> str:
    """Get the nixpkgs source path from the template flake."""
    from vibenix import config
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


@log_function_call("list_available_language_frameworks")
def list_available_language_frameworks() -> List[str]:
    """List all available language and framework documentation files.
    
    Returns:
        List of language/framework names (without .section.md extension)
        
    Raises:
        RuntimeError: If nixpkgs source path cannot be determined
        FileNotFoundError: If the doc/languages-frameworks directory doesn't exist
        PermissionError: If directory access is denied
    """
    print("📞 Function called: list_available_language_frameworks")
    
    try:
        nixpkgs_path = get_nixpkgs_source_path()
    except Exception as e:
        raise RuntimeError(f"Failed to get nixpkgs source path: {e}")
    
    docs_dir = Path(nixpkgs_path) / "doc" / "languages-frameworks"
    
    if not docs_dir.exists():
        raise FileNotFoundError(f"Languages-frameworks documentation directory not found at: {docs_dir}")
    
    if not docs_dir.is_dir():
        raise NotADirectoryError(f"Expected directory but found file at: {docs_dir}")
    
    try:
        # Find all .section.md files and extract the language/framework names
        frameworks = []
        for md_file in docs_dir.glob("*.section.md"):
            # Remove .section.md suffix to get the framework name
            framework_name = md_file.stem.replace(".section", "")
            frameworks.append(framework_name)
        
        return sorted(frameworks)
        
    except PermissionError:
        raise PermissionError(f"Permission denied accessing directory: {docs_dir}")
    except Exception as e:
        raise RuntimeError(f"Error reading language frameworks directory: {str(e)}")


@log_function_call("get_language_framework_overview")
def get_language_framework_overview(framework: str, section_name: str = None) -> str:
    """Get the overview content of a specific language/framework documentation file.
    
    Returns the content with each section and subsection truncated to only show
    the first paragraph, providing a quick overview of the documentation structure.
    If section_name is provided, that specific section is shown in full.
    
    Args:
        framework: The framework name (e.g., "go", "python", "rust")
        section_name: Optional section name to read in full (e.g., "agda-maintaining-packages")
        
    Returns:
        Truncated markdown content showing only the first paragraph of each section,
        or full content for the specified section
        
    Raises:
        RuntimeError: If nixpkgs source path cannot be determined
        FileNotFoundError: If the framework documentation file doesn't exist
        PermissionError: If file access is denied
    """
    print(f"📞 Function called: get_language_framework_overview with framework: {framework}, section_name: {section_name}")
    
    try:
        nixpkgs_path = get_nixpkgs_source_path()
    except Exception as e:
        raise RuntimeError(f"Failed to get nixpkgs source path: {e}")
    
    # Construct the file path
    docs_dir = Path(nixpkgs_path) / "doc" / "languages-frameworks"
    framework_file = docs_dir / f"{framework}.section.md"
    
    if not framework_file.exists():
        raise FileNotFoundError(f"Framework documentation not found: {framework_file}")
    
    if not framework_file.is_file():
        raise FileNotFoundError(f"Expected file but found directory at: {framework_file}")
    
    try:
        # Read the file content
        with open(framework_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Process content
        if section_name:
            return _extract_specific_section(content, section_name)
        else:
            return _truncate_all_sections(content)
        
    except PermissionError:
        raise PermissionError(f"Permission denied reading file: {framework_file}")
    except UnicodeDecodeError as e:
        raise RuntimeError(f"Error decoding file content (not valid UTF-8): {e}")
    except Exception as e:
        raise RuntimeError(f"Error reading framework documentation file: {str(e)}")


def _extract_specific_section(content: str, section_name: str) -> str:
    """Extract only the specified section from the content."""
    lines = content.split('\n')
    result_lines = []
    in_code_block = False
    in_target_section = False
    target_section_level = None
    
    for line in lines:
        stripped_line = line.strip()
        
        # Track code blocks
        if stripped_line.startswith('```') or stripped_line.startswith('~~~'):
            in_code_block = not in_code_block
            if in_target_section:
                result_lines.append(line)
            continue
        
        # Check for headings
        if (stripped_line.startswith('#') and not in_code_block and 
            _is_valid_markdown_heading(stripped_line)):
            
            heading_level = len(stripped_line.split()[0])
            heading_text = stripped_line[heading_level:].strip()
            section_id = _extract_section_id(heading_text)
            
            # Check if we found our target section
            if section_id == section_name:
                in_target_section = True
                target_section_level = heading_level
                result_lines.append(line)
                result_lines.append('')
                continue
            
            # Check if we're leaving the target section
            if in_target_section and heading_level <= target_section_level:
                break  # Stop here, we've left the target section
            
            # Add subsection headings if we're in the target section
            if in_target_section:
                result_lines.append(line)
                result_lines.append('')
            continue
        
        # Add content lines only if we're in the target section
        if in_target_section:
            result_lines.append(line)
    
    if result_lines:
        return f"Here is the content for section '{section_name}':\n" + '\n'.join(result_lines)
    else:
        return f"Section '{section_name}' not found."


def _truncate_all_sections(content: str) -> str:
    """Truncate all sections to show only first paragraph of each."""
    lines = content.split('\n')
    result_lines = []
    current_section_lines = []
    in_code_block = False
    
    for line in lines:
        stripped_line = line.strip()
        
        # Track code blocks
        if stripped_line.startswith('```') or stripped_line.startswith('~~~'):
            in_code_block = not in_code_block
            current_section_lines.append(line)
            continue
        
        # Check for headings
        if (stripped_line.startswith('#') and not in_code_block and 
            _is_valid_markdown_heading(stripped_line)):
            
            # Process previous section
            if current_section_lines:
                result_lines.extend(_get_first_paragraph(current_section_lines) + ["(continues...)\n"])
                current_section_lines = []
            
            # Add heading
            result_lines.append(line)
            result_lines.append('')
            continue
        
        # Accumulate content
        current_section_lines.append(line)
    
    # Process last section
    if current_section_lines:
        result_lines.extend(_get_first_paragraph(current_section_lines) + ["(continues...)\n"])
    
    return "Here is a truncated version of the file:\n" + '\n'.join(result_lines)


def _extract_section_id(heading_text: str) -> str:
    """Extract section ID from heading text, looking for {#section-id} format."""
    import re
    match = re.search(r'\{#([^}]+)\}', heading_text)
    return match.group(1) if match else ""


def _is_valid_markdown_heading(line: str) -> bool:
    """Check if a line starting with # is a valid markdown heading."""
    import re
    return bool(re.match(r'^#{1,6}\s+.+', line.strip()))


def _get_first_paragraph(section_lines: List[str]) -> List[str]:
    """Extract only the first paragraph from a section's content."""
    paragraph_lines = []
    found_content = False
    
    for line in section_lines:
        stripped_line = line.strip()
        
        # Skip empty lines at the beginning
        if not found_content and not stripped_line:
            continue
        
        # Found the start of content
        if not found_content and stripped_line:
            found_content = True
        
        # If we hit an empty line after finding content, we've reached the end of first paragraph
        if found_content and not stripped_line:
            break
        
        # Add the line if we're in the first paragraph
        if found_content:
            paragraph_lines.append(line)
    
    # Add a blank line after the paragraph for spacing
    if paragraph_lines:
        paragraph_lines.append('')
    
    return paragraph_lines


@log_function_call("search_across_language_frameworks")
def search_across_language_frameworks(keyword: str) -> str:
    """Search for a keyword across all language framework documentation files.
    
    Args:
        keyword: The keyword to search for across all framework docs
        
    Returns:
        A list of frameworks that contain the keyword
        
    Raises:
        RuntimeError: If nixpkgs source path cannot be determined
        FileNotFoundError: If the doc/languages-frameworks directory doesn't exist
    """
    print(f"📞 Function called: search_across_language_frameworks with keyword: {keyword}")
    
    try:
        nixpkgs_path = get_nixpkgs_source_path()
    except Exception as e:
        raise RuntimeError(f"Failed to get nixpkgs source path: {e}")
    
    docs_dir = Path(nixpkgs_path) / "doc" / "languages-frameworks"
    
    if not docs_dir.exists():
        raise FileNotFoundError(f"Languages-frameworks documentation directory not found at: {docs_dir}")
    
    # Search across all .section.md files
    matching_frameworks = []
    
    try:
        import re
        # Create case-insensitive regex pattern
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        
        for md_file in docs_dir.glob("*.section.md"):
            framework_name = md_file.stem.replace(".section", "")
            
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Search for keyword using regex
                if pattern.search(content):
                    matching_frameworks.append(framework_name)
                    
            except (PermissionError, UnicodeDecodeError) as e:
                # Skip files we can't read, but don't fail the whole search
                continue
        
        # Format results
        if matching_frameworks:
            frameworks_list = ', '.join(sorted(matching_frameworks))
            return f"Keyword '{keyword}' found in: {frameworks_list} framework documentation."
        else:
            return f"Keyword '{keyword}' not found in any language framework documentation."
            
    except Exception as e:
        raise RuntimeError(f"Error searching language frameworks: {str(e)}")


@log_function_call("find_builder_functions")
def find_builder_functions(langs: List[str]) -> List[str]:
    """Find all builder functions in nixpkgs using regex patterns.

    Returns:
        A sorted list of unique builder functions found in nixpkgs
        
    Raises:
        RuntimeError: If nixpkgs source path cannot be determined or search fails
    """
    print("📞 Function called: find_builder_functions")
    
    # Check for cached results first
    import json
    import tempfile, pathlib
    
    temp_dir = pathlib.Path(tempfile.gettempdir())
    cache_filename = "cache_vibenix_builder_functions.json"
    cache_file = temp_dir / cache_filename
    
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
        helper = { "rust":  "rustPlatform", "dprint": "dprint-plugins", "open": "openmodelica"}
        
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
            print(f"💾 Cached {len(sorted_functions)} builder functions to {cache_file}")
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
    l = match.group().lower()  # e.g., "Go" -> "go"
    if l in helper_map:
        l = helper_map[l]

    import subprocess
    for lang in [l] + langs: # even if the lang guessing fails, try all langs
        # Try different qualified path patterns
        test_paths = [
            # f'pkgs',                  # pkgs.buildGoModule ( DONE BELOW )
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
            f"let pkgs = import <nixpkgs> {{}}; candidates = [{" ".join(f"{{name=\"{path}\"; set=(let r = builtins.tryEval ({path} or null); in if r.success then r.value else null);}}" for path in test_paths)}]; found = builtins.filter (c: c.set != null && c.set ? {function_name}) candidates; in if found != [] then (builtins.head found).name else false"
        ]
        
        try:
            print("TESTE")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.returncode == 0 and result.stdout.strip() != 'false':
                print(f"Found qualified path: {result.stdout.strip()}.{function_name}")
                return f"{result.stdout.strip()}.{function_name}"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            continue # Try next path/lang
    return None


def analyze_builder_usage_patterns(chosen_builders: List[str]) -> str:
    """
    Analyze nixpkgs for builder function usage patterns.
    
    Args:
        chosen_builders: List of builder functions to search for
        
    Returns:
        A formatted string showing builder combination analysis
        
    Raises:
        RuntimeError: If nixpkgs source path cannot be determined or search fails
    """
    print(f"📞 Function called: analyze_builder_usage_patterns with builders: {chosen_builders}")
    
    try:
        nixpkgs_path = get_nixpkgs_source_path()
    except Exception as e:
        raise RuntimeError(f"Failed to get nixpkgs source path: {e}")
    
    # Ensure mkDerivation is included
    all_builders = list(set(chosen_builders + ["pkgs.stdenv.mkDerivation"]))
    
    print(f"Analyzing nixpkgs for builder usage: {all_builders}")
    
    # Data structures
    from collections import defaultdict
    package_to_builders = defaultdict(set)
    builder_to_packages = defaultdict(set)
    
    # Search for each builder function in .nix files
    for builder in all_builders:
        print(f"Searching for {builder}...")
        
        try:
            # Use ripgrep to find .nix files containing the builder function
            import subprocess
            result = subprocess.run([
                "rg",
                "--type", "nix",
                "--files-with-matches",
                rf"\b{builder}\b",
                nixpkgs_path
            ], capture_output=True, text=True, check=True)
            
            files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            print(f"Found {len(files)} files using {builder}")
            
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
        reverse=True
    )
    
    # Format results
    result_lines = []
    result_lines.append("="*80)
    result_lines.append("BUILDER COMBINATION ANALYSIS")
    result_lines.append("="*80)
    
    for combination, packages in sorted_combinations:
        result_lines.append(f"\n{combination} ({len(packages)} packages):")
        result_lines.append("-" * (len(combination) + 20))
        
        # Sort packages alphabetically and limit to first 20 for readability
        sorted_packages = sorted(packages)
        for i, package in enumerate(sorted_packages[:20]):
            result_lines.append(f"  {package}")
        
        if len(sorted_packages) > 20:
            result_lines.append(f"  ... and {len(sorted_packages) - 20} more packages")
    
    # Summary statistics
    result_lines.append("\n" + "="*80)
    result_lines.append("SUMMARY STATISTICS")
    result_lines.append("="*80)
    
    total_packages = len(package_to_builders)
    result_lines.append(f"Total packages analyzed: {total_packages}")
    result_lines.append(f"Total unique combinations: {len(combination_counts)}")
    
    for builder in all_builders:
        count = len(builder_to_packages[builder])
        percentage = (count / total_packages * 100) if total_packages > 0 else 0
        result_lines.append(f"{builder}: {count} packages ({percentage:.1f}%)")
    
    return "\n".join(result_lines)
