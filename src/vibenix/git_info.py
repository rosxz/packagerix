"""Module for retrieving git repository information."""

import subprocess
from pathlib import Path


def get_git_info():
    """Get git commit hash and dirty status.
    
    Returns:
        dict: Dictionary with 'commit_hash' and 'is_dirty' keys.
              Returns None values if not in a git repository.
    """
    try:
        # Get the commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = commit_result.stdout.strip()
        
        # Check if repository is dirty (has uncommitted changes)
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True
        )
        is_dirty = bool(status_result.stdout.strip())
        
        return {
            "commit_hash": commit_hash,
            "is_dirty": is_dirty
        }
    except subprocess.CalledProcessError:
        # Not in a git repository or git command failed
        return {
            "commit_hash": None,
            "is_dirty": None
        }