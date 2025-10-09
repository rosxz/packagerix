#!/usr/bin/env python3

import os
import re
from pathlib import Path

def extract_fetcher_from_ccl(ccl_content):
    """Extract the fetcher block from run.ccl content."""
    lines = ccl_content.split('\n')
    result_lines = []
    in_fetcher_section = False
    
    for i, line in enumerate(lines):
        # Look for the "  fetcher = " line (2 spaces indentation)
        if line.strip() == 'fetcher =' and line.startswith('  '):
            in_fetcher_section = True
            continue
        
        if in_fetcher_section:
            # Check if we've reached the end of the fetcher section (back to 2-space indentation)
            if line.startswith('  ') and not line.startswith('    ') and line.strip():
                # We've hit the next section at the same level, stop
                break
            
            # Process lines that are part of the fetchFromGitHub block (4+ spaces)
            if line.startswith('    '):
                stripped = line.strip()
                if stripped.startswith('fetchFrom'):
                    result_lines.append(stripped)
                elif stripped == '}':
                    result_lines.append(stripped)
                    break  # End of the fetchFrom block
                elif stripped:  # Any other non-empty line inside the block
                    # Convert 6-space indentation to 2-space for clean output
                    if line.startswith('      '):
                        result_lines.append('  ' + stripped)
                    else:
                        result_lines.append(stripped)
    
    if result_lines:
        return '\n'.join(result_lines)
    return None

def parse_directory_name(dir_name):
    """Parse directory name to extract issue number and construct repo URL."""
    # Format: <issue_number>-<repo_owner>-<repo>
    parts = dir_name.split('-', 2)
    if len(parts) >= 3:
        repo_owner = parts[1]
        repo_name = parts[2]
        return repo_owner, repo_name
    return None, None

def main():
    """Main function to extract fetchers from all directories."""
    current_dir = Path('.')
    fetchers_dir = Path('fetchers')
    
    # Create fetchers directory if it doesn't exist
    fetchers_dir.mkdir(exist_ok=True)
    
    count = 0
    
    # Get all directories that match the pattern
    for dir_path in current_dir.iterdir():
        if not dir_path.is_dir() or dir_path.name == 'fetchers':
            continue

        # Skip if directory name doesn't match expected pattern
        repo_owner, repo_name = parse_directory_name(dir_path.name)
        if not repo_owner or not repo_name:
            raise ValueError(f"Directory name {dir_path.name} does not match expected pattern")
            
        # Look for run.ccl file
        ccl_file = dir_path / 'run.ccl'
        if not ccl_file.exists():
            print(f"Warning: {ccl_file} not found")
            continue
            
        try:
            with open(ccl_file, 'r', encoding='utf-8') as f:
                ccl_content = f.read()
                
            fetcher = extract_fetcher_from_ccl(ccl_content)
            if fetcher:
                # Write fetcher to individual file using directory name
                output_file = str(fetchers_dir / f"{repo_owner},{repo_name}") + ".nix"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(fetcher)
                count += 1
            else:
                print(f"Warning: Could not extract fetcher from {ccl_file}")
                
        except Exception as e:
            print(f"Error processing {ccl_file}: {e}")
    
    print(f"Extracted {count} fetchers to {fetchers_dir}/ directory")

if __name__ == '__main__':
    main()
