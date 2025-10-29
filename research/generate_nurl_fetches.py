#!/usr/bin/env python3
import csv
import subprocess
import os
import time
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

def check_github_rate_limit():
    """Check GitHub API rate limit status."""
    try:
        # Get GitHub token from environment variable
        github_token = os.getenv('GITHUB_TOKEN')
        
        # Build curl command with optional auth header
        cmd = ['curl', '-s']
        if github_token:
            cmd.extend(['-H', f'Authorization: token {github_token}'])
        cmd.append('https://api.github.com/rate_limit')
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse JSON response
        import json
        data = json.loads(result.stdout)
        
        rate_remaining = data['rate']['remaining']
        rate_reset = data['rate']['reset']
        
        if rate_remaining is not None and rate_reset is not None:
            reset_time = datetime.fromtimestamp(rate_reset)
            return rate_remaining, reset_time
        
        # If we can't get rate limit info, assume we're rate limited
        return 0, None
        
    except Exception as e:
        print(f"Warning: Could not check rate limit: {e}")
        # If rate limit check fails, assume we're rate limited
        return 0, None

def wait_for_rate_limit_reset(reset_time):
    """Wait until rate limit resets."""
    if reset_time:
        wait_seconds = (reset_time - datetime.now()).total_seconds()
        if wait_seconds > 0:
            print(f"\nRate limit exceeded. Waiting until {reset_time.strftime('%Y-%m-%d %H:%M:%S')} ({wait_seconds:.0f} seconds)...")
            time.sleep(wait_seconds + 5)  # Add 5 seconds buffer

def run_nurl(url, rev=None):
    """Run nurl command and return the output."""
    try:
        # Get GitHub token from environment variable
        github_token = os.getenv('GITHUB_TOKEN')
        
        # Build nurl command
        cmd = ['nurl', url, rev] if rev else ['nurl', url]
        
        # Set up environment for nurl with GitHub token
        env = os.environ.copy()
        if github_token:
            env['GITHUB_TOKEN'] = github_token
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env=env
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.lower()
        print(f"nurl error output: {error_output}")
        # Check for genuine rate limit indicators
        if any(indicator in error_output for indicator in ["rate limit", "429"]):
            print(f"Rate limit error for {url}")
            return "RATE_LIMITED"
        # Check for 403/forbidden but don't assume it's rate limiting
        print(f"Error running nurl for {url}: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Error: nurl command not found. Please ensure nurl is installed.")
        return None

def extract_repo_info(repo_url):
    """Extract owner and repo name from GitHub URL."""
    try:
        # Handle various GitHub URL formats
        if 'github.com' in repo_url:
            # Remove protocol and split
            url_parts = repo_url.replace('https://', '').replace('http://', '').split('/')
            if len(url_parts) >= 3:
                owner = url_parts[1]
                repo = url_parts[2].replace('.git', '')  # Remove .git suffix if present
                return owner, repo
    except Exception:
        pass
    return None, None

def process_csv_file(csv_path, output_dir):
    """Process a CSV file and generate .nix files for each URL."""
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        github_request_count = 0
        
        for row in reader:
            repo_url = row['repo_url']
            revision = row.get('revision', None)
            
            # Skip rows without URLs
            if not repo_url:
                print(f"Skipping row: No URL provided")
                continue
            
            # Extract repo owner and name
            owner, repo_name = extract_repo_info(repo_url)
            if not owner or not repo_name:
                print(f"Skipping {repo_url}: Could not extract owner/repo name")
                continue
            
            # Create filename as owner,repo_name.nix
            output_file = output_dir / f"{owner},{repo_name}.nix"
            if output_file.exists():
                print(f"Skipping {owner}/{repo_name}: File already exists")
                continue
            
            # Check rate limit before processing GitHub URLs
            if 'github.com' in repo_url:
                remaining, reset_time = check_github_rate_limit()
                print(f"\nGitHub rate limit: {remaining} requests remaining")
                if remaining <= 1:
                    wait_for_rate_limit_reset(reset_time)
                    # Re-check after waiting
                    remaining, reset_time = check_github_rate_limit()
                    print(f"After waiting - GitHub rate limit: {remaining} requests remaining")
            
            print(f"Processing {owner}/{repo_name}: {repo_url}")
            
            # Run nurl to generate fetch expression
            fetch_expr = run_nurl(repo_url, revision)
            
            if fetch_expr == "RATE_LIMITED":
                # Check rate limit and wait
                _, reset_time = check_github_rate_limit()
                wait_for_rate_limit_reset(reset_time)
                # Retry after waiting
                fetch_expr = run_nurl(repo_url, revision)
            
            if fetch_expr and fetch_expr != "RATE_LIMITED":
                # Write to owner,repo_name.nix file
                with open(output_file, 'w') as f:
                    f.write(f"# Repository: {owner}/{repo_name}\n")
                    f.write(f"# URL: {repo_url}\n")
                    f.write(fetch_expr)
                    f.write("\n")
                print(f"  → Written to {output_file}")
            else:
                print(f"  → Failed to generate fetch expression")

def main():
    parser = argparse.ArgumentParser(description='Generate nurl fetch expressions from CSV files')
    parser.add_argument('directory', help='Relative directory containing CSV files (relative to script location)')
    args = parser.parse_args()
    
    # Get the directory containing the CSV files
    base_dir = Path(__file__).parent
    csv_dir = base_dir / args.directory
    
    if not csv_dir.exists():
        print(f"Error: Directory {csv_dir} does not exist")
        sys.exit(1)
    
    # Create output directory based on input directory name
    output_dir = csv_dir / "fetchers"
    output_dir.mkdir(exist_ok=True)
    
    # Process CSV files in the directory
    csv_files = list(csv_dir.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {csv_dir}")
        sys.exit(1)
    
    # Check for GitHub token
    github_token = os.getenv('GITHUB_TOKEN')
    if github_token:
        print("GitHub token found - using authenticated requests for higher rate limits")
    else:
        print("No GITHUB_TOKEN environment variable found - using unauthenticated requests")
        print("Set GITHUB_TOKEN for higher rate limits: export GITHUB_TOKEN=your_token_here")
    
    print("\nGitHub rate limit handling:")
    print("- Checks rate limit every 10 GitHub requests")
    print("- Automatically waits if rate limit is exceeded")
    print("- Already processed files will be skipped")
    print("- Non-GitHub URLs are processed without rate limit checks\n")
    
    # Check initial rate limit
    remaining, reset_time = check_github_rate_limit()
    print(f"Initial GitHub rate limit: {remaining} requests remaining\n")
    
    for csv_path in csv_files:
        print(f"\nProcessing {csv_path.name}...")
        process_csv_file(csv_path, output_dir)
    
    print(f"\nCompleted! Fetch expressions saved to {output_dir}/")

if __name__ == "__main__":
    main()
