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


@log_function_call("list_language_frameworks")
def list_language_frameworks() -> List[str]:
    """View list of all available language and frameworks with documentation files in nixpkgs.
    
    Returns:
        List of language/framework names
        
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
def get_language_framework_overview(framework: str) -> str: # , section_name: str = None
    """Get the overview content of a specific language/framework documentation file.
    To obtain a list of available frameworks, use the list_available_language_frameworks tool.
    
    Returns the available documentation in nixpkgs on the specified framework or language.

    Args:
        framework: The framework name (e.g., "go", "python", "rust")
        
    Returns:
        Markdown content on the requested framework or language.
    """
    print(f"📞 Function called: get_language_framework_overview with framework: {framework}") # , section_name: {section_name}
    
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
        return content
        #if section_name:
        #    return _extract_specific_section(content, section_name)
        #else:
        #    return _truncate_all_sections(content)
        
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
                first_paragraph = _get_first_paragraph(current_section_lines)
                result_lines.extend(first_paragraph + (["(continues...)\n"] if len(first_paragraph) > 0 else []))
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
