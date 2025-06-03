import re

import requests
from bs4 import BeautifulSoup
import re
import json

from diskcache import Cache
from app.logging_config import logger

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
        logger.error("No section delimited by triple backticks was found. Should we pass this back to the model?")
        assert (False)
    else:
        logger.error("Reply contained more than one quoted section")
        assert (False)