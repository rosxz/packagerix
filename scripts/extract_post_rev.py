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


def extract_ref_from_fetcher(fetcher_content: str, version: str) -> tuple[str, str] | tuple[None, None]:
    """Extract the rev or tag value from fetcher content.
    
    Returns (attr, value) tuple where attr is 'rev' or 'tag'.
    
    Handles various patterns:
    - rev = "v${version}"; -> resolves ${version} to actual version
    - tag = "v${finalAttrs.version}"; -> resolves to actual version  
    - rev = "abc123def"; -> returns literal value
    - tag = finalAttrs.version; -> resolves to version (no quotes)
    - rev = version; -> resolves to version (no quotes)
    """
    if not fetcher_content:
        return None, None
    
    # Replace the special newline marker with actual newlines for easier parsing
    content = fetcher_content.replace("␤", "\n")
    
    # Try to find rev = "..." or tag = "..." patterns (quoted values)
    quoted_match = re.search(r'(rev|tag)\s*=\s*"([^"]+)"', content)
    if quoted_match:
        attr = quoted_match.group(1)
        value = quoted_match.group(2)
        # Check if it contains version interpolation (with ${} braces)
        if "${version}" in value:
            return attr, value.replace("${version}", version)
        elif "${finalAttrs.version}" in value:
            return attr, value.replace("${finalAttrs.version}", version)
        else:
            # It's a literal value (like a commit hash)
            return attr, value
    
    # Pattern: rev/tag = finalAttrs.version; (no quotes, direct reference)
    unquoted_finalattrs = re.search(r'(rev|tag)\s*=\s*finalAttrs\.version\s*;', content)
    if unquoted_finalattrs:
        return unquoted_finalattrs.group(1), version
    
    # Pattern: rev/tag = version; (no quotes)
    unquoted_version = re.search(r'(rev|tag)\s*=\s*version\s*;', content)
    if unquoted_version:
        return unquoted_version.group(1), version
    
    return None, None


def get_src_ref_nix_eval(commit: str, pname: str) -> tuple[str, str] | tuple[None, None]:
    """Fallback use nix eval to get src.rev or src.tag from nixpkgs flake at given commit."""

    flake_ref = f"github:NixOS/nixpkgs/{commit}"
    
    # Try src.rev first (most common)
    for attr in ["rev", "tag"]:
        try:
            result = subprocess.run(
                ["nix", "eval", "--raw", f"{flake_ref}#{pname}.src.{attr}"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                return attr, result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"  Timeout evaluating {pname}.src.{attr}", file=sys.stderr)
        except Exception as e:
            print(f"  Error evaluating {pname}.src.{attr}: {e}", file=sys.stderr)
    return None, None


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
    attr_col = args.column_name + "_attr"
    nurl_col = "nurl_supported"
    
    fieldnames = list(fieldnames)
    for col in [ref_col, attr_col, nurl_col]:
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
        commit = row.get('commit_hash', '')
        pname = row.get('post_pname', row.get('pre_pname', ''))
        
        # Check if fetcher is supported by nurl
        fetcher_name = extract_fetcher_name(post_fetcher)
        if supported_fetchers and fetcher_name:
            is_supported = fetcher_name in supported_fetchers
            if not is_supported:
                # Fetcher not supported by nurl - skip extraction
                row[nurl_col] = f"no ({fetcher_name})"
                row[ref_col] = "UNSUPPORTED_FETCHER"
                row[attr_col] = "UNSUPPORTED_FETCHER"
                unsupported_count += 1
                print(f"[{i}/{total}] {pname} -> UNSUPPORTED_FETCHER ({fetcher_name})")
                continue
            row[nurl_col] = "yes"
        else:
            row[nurl_col] = "unknown"
        
        # Try regex first
        attr, ref = extract_ref_from_fetcher(post_fetcher, post_version)
        
        if ref:
            extracted_count += 1
            print(f"[{i}/{total}] {pname} -> {attr}={ref}")
        else:
            # Fallback to nix eval
            print(f"[{i}/{total}] {pname} -> regex failed, trying nix eval...", end=" ", flush=True)
            attr, ref = get_src_ref_nix_eval(commit, pname)
            if ref:
                extracted_count += 1
                print(f"{attr}={ref}")
            else:
                failed_count += 1
                print("FAILED")
        
        row[ref_col] = ref or ''
        row[attr_col] = attr or ''

    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nProcessed {total} rows:")
    print(f"  - Successfully extracted: {extracted_count}")
    print(f"  - Unsupported fetcher (skipped): {unsupported_count}")
    print(f"  - Failed to extract: {failed_count}")
    print(f"\nOutput written to: {output_path}")


if __name__ == "__main__":
    main()
