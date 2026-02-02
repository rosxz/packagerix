#!/usr/bin/env python3
"""Extract package contents at pre-update state from a maintenance CSV dataset.

Usage:
    python extract_pre_packages.py research/maintenance_02_02_2025.csv

Requires a nixpkgs clone at ~/nixpkgs.
Outputs package.nix files to pkg_contents/ directory as {pre_pname}.nix
"""

import argparse
import csv
import subprocess
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Extract pre-update package contents from CSV")
    parser.add_argument("csv_file", help="Path to the maintenance CSV file")
    parser.add_argument("--nixpkgs", default=Path.home() / "nixpkgs", help="Path to nixpkgs clone (default: ~/nixpkgs)")
    parser.add_argument("--output", default="pkg_contents", help="Output directory (default: pkg_contents)")
    args = parser.parse_args()

    nixpkgs_path = Path(args.nixpkgs)
    output_dir = Path(args.output)
    
    if not nixpkgs_path.exists():
        print(f"Error: nixpkgs not found at {nixpkgs_path}")
        return 1
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read CSV
    with open(args.csv_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Processing {len(rows)} packages...")
    
    for i, row in enumerate(rows, 1):
        pname = row['pre_pname']
        parent_commit = row['parent_commit']
        package_path = row['package_path']
        
        print(f"[{i}/{len(rows)}] {pname} @ {parent_commit[:8]}...")
        
        try:
            # Get the package.nix content at the parent commit
            result = subprocess.run(
                ["git", "show", f"{parent_commit}:{package_path}"],
                cwd=nixpkgs_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Write to output file
            output_file = output_dir / f"{pname}.nix"
            output_file.write_text(result.stdout)
            print(f"    -> {output_file}")
            
        except subprocess.CalledProcessError as e:
            print(f"    ERROR: {e.stderr.strip()}")
            continue
    
    print(f"\nDone! Output in {output_dir}/")


if __name__ == "__main__":
    main()
