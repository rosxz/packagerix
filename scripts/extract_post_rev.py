#!/usr/bin/env python3
"""Extract rev/tag from post_fetcher_content and add as new columns to CSV.

This script reads a maintenance CSV dataset and extracts the `rev` or `tag`
value from each entry's post_fetcher_content, adding columns for the ref value
and which attribute it came from (rev or tag).

Usage:
    python extract_post_rev.py research/maintenance_02_02_2025.csv

Output:
    Creates a new CSV file with '_with_ref' suffix (e.g., maintenance_02_02_2025_with_ref.csv)
"""

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


def extract_ref_from_fetcher(fetcher_content: str, version: str) -> str | None:
    """Extract the rev or tag value from fetcher content."""
    if not fetcher_content:
        return None
    
    # Replace the special newline marker with actual newlines for easier parsing
    content = fetcher_content.replace("␤", "\n")
    
    # Try to find rev = "..." or tag = "..." patterns (quoted values)
    quoted_match = re.search(r'(rev|tag)\s*=', content)
    if quoted_match:
        attr = quoted_match.group(1)
        return attr
    
    return None


def get_src_ref_nix_eval(commit: str, package_attr: str) -> str | None:
    """Fallback use nix eval to get src.rev or src.tag from nixpkgs flake at given commit."""

    flake_ref = f"github:NixOS/nixpkgs/{commit}"

    def run_eval(cmd: str) -> str | None:
        try:
            result = subprocess.run(
                ["nix", "eval", "--raw", cmd],
                capture_output=True,
                text=True,
                timeout=90,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            pass
        return None
    
    for attr in ['rev', 'tag']:
        eval = run_eval(f"{flake_ref}#{package_attr}.src.{attr}")
        if eval:
            return eval
    return run_eval(f"{flake_ref}#{package_attr}.version") # Fallback: go with version (PyPi)


def get_nurl_supported_fetchers() -> set[str]:
    """Get list of fetchers supported by nurl."""
    try:
        result = subprocess.run(
            ["nurl", "-l"],
            capture_output=True,
            text=True,
            check=True,
        )
        return set(result.stdout.strip().split('\n'))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Could not get nurl supported fetchers: {e}", file=sys.stderr)
        return set()


def extract_fetcher_name(fetcher_content: str) -> str | None:
    """Extract the fetcher function name from fetcher content (e.g., 'fetchFromGitHub')."""
    if not fetcher_content:
        return None
    content = fetcher_content.replace("␤", "\n")
    match = re.match(r'(fetch\w+)\s*\{', content.strip())
    return match.group(1) if match else None


def main():
    parser = argparse.ArgumentParser(
        description="Extract rev/tag from post_fetcher_content and add as new columns"
    )
    parser.add_argument("csv_file", help="Path to the maintenance CSV file")
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: input_with_ref.csv)"
    )
    parser.add_argument(
        "--column-name",
        default="post_src_ref",
        help="Name for the new column (default: post_src_ref)"
    )
    parser.add_argument(
        "--in-place", "-i",
        action="store_true",
        help="Modify the input file in place"
    )
    args = parser.parse_args()

    input_path = Path(args.csv_file)
    
    if args.in_place:
        output_path = input_path
    elif args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_stem(input_path.stem + "_with_ref")

    # Read the CSV
    with open(input_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames:
        print("Error: CSV file appears to be empty or has no headers")
        return 1

    # Check if columns already exist
    ref_col = args.column_name
    nurl_col = "nurl_supported"
    
    fieldnames = list(fieldnames)
    for col in [ref_col, nurl_col]:
        if col in fieldnames:
            print(f"Warning: Column '{col}' already exists, will be overwritten")
        else:
            fieldnames.append(col)
    
    # Get nurl-supported fetchers
    supported_fetchers = get_nurl_supported_fetchers()
    if supported_fetchers:
        print(f"nurl supports {len(supported_fetchers)} fetchers: {', '.join(sorted(supported_fetchers))}")
    else:
        print("Warning: Could not determine nurl-supported fetchers, skipping check")

    # Process each row
    extracted_count = 0
    failed_count = 0
    unsupported_count = 0
    total = len(rows)
    
    for i, row in enumerate(rows, 1):
        post_fetcher = row.get('post_fetcher_content', '')
        post_version = row.get('post_version', '')
        post_nixpkgs_base = row.get('post_nixpkgs_base', '')
        package_attr = row.get('package_attr', row.get('fully_qualified_name', ''))
        
        # Check if fetcher is supported by nurl
        fetcher_name = extract_fetcher_name(post_fetcher)
        if supported_fetchers and fetcher_name:
            is_supported = fetcher_name in supported_fetchers
            if not is_supported:
                # Fetcher not supported by nurl - skip extraction
                row[nurl_col] = f"no ({fetcher_name})"
                row[ref_col] = "UNSUPPORTED_FETCHER"
                unsupported_count += 1
                print(f"[{i}/{total}] {package_attr} -> UNSUPPORTED_FETCHER ({fetcher_name})")
                continue
            row[nurl_col] = "yes"
        else:
            row[nurl_col] = "unknown"
        
        ref = get_src_ref_nix_eval(post_nixpkgs_base, package_attr)
        if ref:
            print(f"[{i}/{total}] {package_attr} -> {ref}")
            extracted_count += 1
        else:
            print(f"[{i}/{total}] {package_attr} -> FAIL")
            failed_count += 1
        
        row[ref_col] = ref or ''

    for row in rows:
        if None in row:
            del row[None]
    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nProcessed {total} rows:")
    print(f"  - Successfully extracted: {extracted_count}")
    print(f"  - Unsupported fetcher (skipped): {unsupported_count}")
    print(f"  - Failed to extract: {failed_count}")
    print(f"\nOutput written to: {output_path}")


if __name__ == "__main__":
    main()
