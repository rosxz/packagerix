import re

import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urlparse
import subprocess

from diskcache import Cache
from vibenix.ui.logging_config import logger
from jinja2 import Template

cache = Cache("cachedir")

@cache.memoize()
def scrape_and_process(url):
    # Fetch the webpage content
    response = requests.get(url)
    html = response.text

    # Parse the HTML content
    soup = BeautifulSoup(html, 'html.parser')

    # Remove all <script> and <style> elements
    for script_or_style in soup(['script', 'style']):
        script_or_style.decompose()
    
    # Remove elements that are often irrelevant like headers, footers, and navs
    tags_to_remove = ['header', 'nav', 'footer', 'aside']
    for tag in tags_to_remove:
        for element in soup.find_all(tag):
            element.decompose()

    # Extract text from the webpage
    # You might need to adjust the selection to your specific needs
    text = ' '.join(soup.stripped_strings)

    # Basic cleanup to remove unwanted characters or sections
    cleaned_text = re.sub(r'\s+', ' ', text)  # Remove extra whitespaces

    return cleaned_text

def fetch_github_release_data(url):
    """Fetch release data from GitHub API for the given repository URL."""
    # Parse the GitHub URL to extract owner and repo
    parsed_url = urlparse(url)
    if parsed_url.netloc != 'github.com':
        logger.warning(f"Not a GitHub URL: {url}")
        return None
    
    path_parts = parsed_url.path.strip('/').split('/')
    if len(path_parts) < 2:
        logger.warning(f"Invalid GitHub URL format: {url}")
        return None
    
    owner = path_parts[0]
    repo = path_parts[1]
    
    # Fetch latest release data from GitHub API
    # NOTE: To simplify the threat model, we only fetch auto-generated release artifacts
    # (tarball_url, zipball_url) and not user-uploaded assets. This ensures we're only
    # getting source code directly from GitHub's servers.
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    
    try:
        response = requests.get(api_url, headers={'Accept': 'application/vnd.github.v3+json'})
        response.raise_for_status()
        release_data = response.json()

        return release_data.get('tag_name')
    except requests.RequestException as e:
        logger.error(f"Failed to fetch release data from GitHub API: {e}")
        return None

def extract_src_attributes(src_attr, release=None):
    """Extract version, repo and hash from a src_attr."""
    if not (match := re.search(r'repo\s*=\s*"(.*?)";\s*rev\s*=\s*"(.*?)";\s*hash\s*=\s*"(.*?)"', src_attr)):
        logger.error("Could not extract revision or hash from src_attr")
        raise ValueError("Could not extract revision or hash from src_attr")
    else:
        repo = match.group(1)
        rev = match.group(2)
        hash = match.group(3)
    if release:
        rev = release
    # Try to extract version from the release following semantic versioning rules
    version = None
    pattern = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    match = re.search(pattern, rev.lstrip('v'))
    if match:
        version = match.group(0)
        # Substitute the version in the source_attr for ${version}
        new_rev = rev.replace(version, "${version}")
        src_attr = src_attr.replace(f'"{rev}"', f'"{new_rev}"')
    else:
        # use the full git revision if we don't have a named version
        # (depends on using rec { ... } in the temlate)
        version = f"{release or 'unstable'}-${{src.rev}}"

    return version, repo, hash, src_attr

def fill_src_attributes(template, pname, version, src_fetcher):
    """Fill the pname, version and src attributes in a given template."""
    # Extract hash from the fetcher to compute store path
    hash_match = re.search(r'hash\s*=\s*"(.*?)"', src_fetcher)
    if not hash_match:
        logger.error("Could not extract hash from fetcher")
        raise ValueError("Could not extract hash from fetcher")
    
    hash = hash_match.group(1)
    
    # Get the store path
    store_path = subprocess.run(["nix-store", "--print-fixed-path", "sha256",
                                 "--recursive", hash, "source"],
                                 capture_output=True, text=True)
    store_path = str(store_path.stdout).strip()

    jinja_template = Template(template)
    filled_template = jinja_template.render(
        pname=pname,
        version=version,
        src_fetcher=src_fetcher
    )
    from vibenix.flake import update_flake
    update_flake(filled_template)
    
    logger.info(f"Filled template: \n{filled_template}")
    
    return filled_template, store_path

def fetch_combined_project_data(url):
    """Fetch both HTML and API data for a GitHub project."""
    # Get HTML content
    html_content = scrape_and_process(url)
    
    # Get API release data
    release_data = fetch_github_release_data(url)
    
    # Combine the data
    combined_data = f"{html_content}\n\n"
    
    if release_data:
        combined_data += "--- GitHub Release Information ---\n"
        combined_data += f"Latest release/tag: {release_data.get('tag_name', 'N/A')}\n"
        
        if release_data.get('name'):
            combined_data += f"Release name: {release_data['name']}\n"
        
        if release_data.get('published_at'):
            combined_data += f"Published at: {release_data['published_at']}\n"
        
        combined_data += f"Source tarball: {release_data.get('tarball_url', 'N/A')}\n"
        combined_data += f"Source zipball: {release_data.get('zipball_url', 'N/A')}\n"
        
        if release_data.get('assets'):
            combined_data += "\nRelease assets:\n"
            for asset in release_data['assets']:
                combined_data += f"  - {asset['name']}: {asset['browser_download_url']}\n"
        
        combined_data += f"\nData source: {release_data.get('source', 'unknown')}\n"
    else:
        combined_data += "\n--- No GitHub Release Information Available ---\n"
    
    return combined_data

def extract_updated_code(model_reply, language: str = None):
    """
    Extract code from the last code block in the model reply.
    
    Args:
        model_reply: The model's response text
        language: Optional language identifier (e.g., 'nix', 'python'). 
                 If None, extracts from any code block.
    
    Returns:
        The extracted code content
    """
    if language:
        pattern = rf"```{re.escape(language)}\n(.*?)\n```"
    else:
        pattern = r"```(?:\w+)?\n(.*?)\n```"
    
    matches = list(re.finditer(pattern, model_reply, re.DOTALL))
    if len(matches) == 0:
        error_msg = "No section delimited by triple backticks was found in the model's reply"
        logger.error(error_msg)
        raise ValueError(error_msg)
    elif len(matches) > 1:
        logger.warning(f"Reply contained {len(matches)} quoted sections, using the last one")
    
    return matches[-1].group(1)
