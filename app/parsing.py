import re

import requests
from bs4 import BeautifulSoup
import re
import json

from diskcache import Cache
from app.ui.logging_config import logger

cache = Cache("cachedir")

@cache.memoize()
def scrape_and_process(url):
    # Fetch the webpage content
    response = requests.get(url)
    html = response.text

    # Parse the HTML content
    soup = BeautifulSoup(html, 'html.parser')

    # Extract text from the webpage
    # You might need to adjust the selection to your specific needs
    text = ' '.join(soup.stripped_strings)

    # Basic cleanup to remove unwanted characters or sections
    cleaned_text = re.sub(r'\s+', ' ', text)  # Remove extra whitespaces

    return cleaned_text

def extract_updated_code(model_reply):
    pattern = r"^```nix\n(.*?)\n```$"

    matches = list(re.finditer(pattern, model_reply, re.DOTALL | re.MULTILINE))
    if len(matches) == 1:
        return matches[0].group(1)
    elif len(matches) == 0:
        error_msg = "No section delimited by triple backticks was found in the model's reply"
        logger.error(error_msg)
        raise ValueError(error_msg)
    else:
        error_msg = f"Reply contained {len(matches)} quoted sections, expected exactly 1"
        logger.error(error_msg)
        raise ValueError(error_msg)