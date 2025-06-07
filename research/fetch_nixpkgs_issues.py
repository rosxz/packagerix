#!/usr/bin/env python3
"""
Fetch packaging request issues from nixpkgs repository and segment them into two CSV files.
"""

import csv
import re
import requests
from typing import List, Tuple, Optional
import time
import os

def get_packaging_request_issues(per_page: int = 100, max_pages: int = 2) -> List[dict]:
    """
    Fetch open packaging request issues from nixpkgs repository.
    """
    issues = []
    page = 1
    
    # GitHub API endpoint for nixpkgs issues
    base_url = "https://api.github.com/repos/NixOS/nixpkgs/issues"
    
    # Headers for GitHub API (add token if you have one)
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "NixpkgsPackagingRequestFetcher/1.0"
    }
    
    # Add GitHub token if available in environment
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    while page <= max_pages:
        params = {
            "state": "open",
            "labels": "0.kind: packaging request",
            "per_page": per_page,
            "page": page,
            "sort": "created",
            "direction": "desc"
        }
        
        print(f"Fetching page {page}...")
        response = requests.get(base_url, headers=headers, params=params)
        
        if response.status_code == 403:
            print("Rate limit exceeded. Please set GITHUB_TOKEN environment variable.")
            break
        elif response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break
        
        page_issues = response.json()
        if not page_issues:
            break
            
        issues.extend(page_issues)
        page += 1
        
        # Respect rate limiting
        time.sleep(1)
    
    return issues

def extract_repo_url(issue_body: str) -> Optional[str]:
    """
    Extract repository URL from issue body using various patterns.
    """
    if not issue_body:
        return None
    
    # Blacklisted URLs to exclude
    blacklisted_urls = [
        'https://github.com/NixOS/nixpkgs',
        'http://github.com/NixOS/nixpkgs',
    ]
    
    # Common patterns for repository URLs
    patterns = [
        r'https?://github\.com/[\w-]+/[\w.-]+',
        r'https?://gitlab\.com/[\w-]+/[\w.-]+',
        r'https?://codeberg\.org/[\w-]+/[\w.-]+',
        r'https?://sr\.ht/~[\w-]+/[\w.-]+',
        r'https?://bitbucket\.org/[\w-]+/[\w.-]+',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, issue_body, re.IGNORECASE)
        if match:
            url = match.group(0)
            # Clean up URL (remove .git suffix if present)
            if url.endswith('.git'):
                url = url[:-4]
            
            # Check if URL is blacklisted
            if url in blacklisted_urls:
                continue
                
            return url
    
    return None

def segment_issues(issues: List[dict]) -> Tuple[List[Tuple[int, Optional[str]]], List[Tuple[int, Optional[str]]]]:
    """
    Segment issues into two lists based on even/odd issue numbers.
    Returns (even_issues, odd_issues) where each item is (issue_number, repo_url).
    """
    even_issues = []
    odd_issues = []
    
    for issue in issues:
        issue_number = issue['number']
        issue_body = issue.get('body', '')
        repo_url = extract_repo_url(issue_body)
        
        if issue_number % 2 == 0:
            even_issues.append((issue_number, repo_url))
        else:
            odd_issues.append((issue_number, repo_url))
    
    return even_issues, odd_issues

def write_csv(filename: str, data: List[Tuple[int, Optional[str]]]):
    """
    Write issue data to CSV file.
    """
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['issue_number', 'repo_url'])
        for issue_number, repo_url in data:
            writer.writerow([issue_number, repo_url or ''])

def main():
    """
    Main function to fetch and segment nixpkgs packaging request issues.
    """
    print("Fetching packaging request issues from nixpkgs...")
    
    # Fetch issues (adjust per_page and max_pages to get ~100 total issues)
    issues = get_packaging_request_issues(per_page=100, max_pages=1)
    
    if not issues:
        print("No issues found.")
        return
    
    print(f"Found {len(issues)} issues total.")
    
    # Segment issues
    even_issues, odd_issues = segment_issues(issues)
    
    print(f"Even-numbered issues (training): {len(even_issues)}")
    print(f"Odd-numbered issues (evaluation): {len(odd_issues)}")
    
    # Write to CSV files
    write_csv('nixpkgs_packaging_requests_training.csv', even_issues)
    write_csv('nixpkgs_packaging_requests_evaluation.csv', odd_issues)
    
    print("\nFiles created:")
    print("- nixpkgs_packaging_requests_training.csv (even issue numbers)")
    print("- nixpkgs_packaging_requests_evaluation.csv (odd issue numbers)")
    
    # Print summary statistics
    even_with_urls = sum(1 for _, url in even_issues if url)
    odd_with_urls = sum(1 for _, url in odd_issues if url)
    
    print(f"\nRepository URLs found:")
    print(f"- Training set: {even_with_urls}/{len(even_issues)}")
    print(f"- Evaluation set: {odd_with_urls}/{len(odd_issues)}")

if __name__ == "__main__":
    main()