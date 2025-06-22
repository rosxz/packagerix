#!/usr/bin/env python3
import csv
import subprocess
import os
import time
import json
from pathlib import Path
from datetime import datetime

def check_github_rate_limit():
    """Check GitHub API rate limit status."""
    try:
        # Use curl to check rate limit
        result = subprocess.run(
            ['curl', '-s', 'https://api.github.com/rate_limit'],
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

def run_nurl(url):
    """Run nurl command and return the output."""
    try:
        result = subprocess.run(
            ['nurl', url],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.lower()
        # Check for various rate limit indicators
        if any(indicator in error_output for indicator in ["rate limit", "429", "403", "forbidden"]):
            print(f"Rate limit/forbidden error for {url}")
            return "RATE_LIMITED"
        print(f"Error running nurl for {url}: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Error: nurl command not found. Please ensure nurl is installed.")
        return None

def process_csv_file(csv_path, output_dir):
    """Process a CSV file and generate .nix files for each URL."""
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        github_request_count = 0
        
        for row in reader:
            issue_number = row['issue_number']
            repo_url = row['repo_url']
            
            # Skip rows without URLs
            if not repo_url:
                print(f"Skipping issue {issue_number}: No URL provided")
                continue
            
            # Check if output file already exists
            output_file = output_dir / f"{issue_number}.nix"
            if output_file.exists():
                print(f"Skipping issue {issue_number}: File already exists")
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
            
            print(f"Processing issue {issue_number}: {repo_url}")
            
            # Run nurl to generate fetch expression
            fetch_expr = run_nurl(repo_url)
            
            if fetch_expr == "RATE_LIMITED":
                # Check rate limit and wait
                _, reset_time = check_github_rate_limit()
                wait_for_rate_limit_reset(reset_time)
                # Retry after waiting
                fetch_expr = run_nurl(repo_url)
            
            if fetch_expr and fetch_expr != "RATE_LIMITED":
                # Write to [issue_number].nix file
                with open(output_file, 'w') as f:
                    f.write(f"# Issue {issue_number}\n")
                    f.write(f"# URL: {repo_url}\n")
                    f.write(fetch_expr)
                    f.write("\n")
                print(f"  → Written to {output_file}")
            else:
                print(f"  → Failed to generate fetch expression")

def main():
    # Get the directory containing the CSV files
    base_dir = Path(__file__).parent
    csv_dir = base_dir / "packaging_requests"
    
    # Create output directory
    output_dir = base_dir / "nurl_fetches"
    output_dir.mkdir(exist_ok=True)
    
    # Process both CSV files
    csv_files = [
        "post_project_evaluation.csv",
        "used_during_implementation.csv"
    ]
    
    print("GitHub rate limit handling:")
    print("- Checks rate limit every 10 GitHub requests")
    print("- Automatically waits if rate limit is exceeded")
    print("- Already processed files will be skipped")
    print("- Non-GitHub URLs are processed without rate limit checks\n")
    
    # Check initial rate limit
    remaining, reset_time = check_github_rate_limit()
    print(f"Initial GitHub rate limit: {remaining} requests remaining\n")
    
    for csv_file in csv_files:
        csv_path = csv_dir / csv_file
        if csv_path.exists():
            print(f"\nProcessing {csv_file}...")
            process_csv_file(csv_path, output_dir)
        else:
            print(f"Warning: {csv_path} not found")
    
    print(f"\nCompleted! Fetch expressions saved to {output_dir}/")

if __name__ == "__main__":
    main()