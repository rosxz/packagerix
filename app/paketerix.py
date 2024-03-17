# https://github.com/jackmpcollins/magentic

from pydantic import BaseModel

from magentic import prompt

from pathlib import Path

import os

os.environ["ANTHROPIC_API_KEY"] = "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"

import litellm

from tools.nix import *
from tools.generic import *
from util.nix import *
from util.generic import *

#litellm.set_verbose=True

# Function calling is not supported by anthropic. To add it to the prompt, set
#litellm.add_function_to_prompt = True #.
#litellm.drop_params=True

starting_template = Path("./template/package.nix").read_text()

#test_project_page = Path("./compose.html").read_text()


# read build log of previous step and this step
# to evalute if the model made progress towards building the project
# this is done by counting magical phrases in the build output like
# "comiling ..." 
# a significantly higher number of magical phrases indicates progress
# an about equal amount goes to an llm to break the tie using same_build_error with the two tails of the two build logs
def eval_progress() -> bool : ...

def build_package(source : str) -> bool : ...

def eval_build(source: str) -> str : ... #, prev_log: str

def find_source(name: str) -> str:
    return input (f"Dear human, please fill the automation gap and input the github page of {name}.")

def package_missing_dependency (name: str): pass
    # itentify source
    # recurse into original process
    #   - init new git template
    #   - read github repo
    #   - everything

@prompt("""
Make a targeted and incremental addition to the existing Nix derivation so that the build progesses further,
by filling in the data marked with ... .
This is the code you are starting from:

```nix
{prev_working_code}
```

Fill in the correct information from the project's github page listed here:

```text
{test_project_page}
```

When you think you are done, invoke the test_updated_code function with the updated code.

""",
functions=[test_updated_code, search_nixpkgs_for_package, package_missing_dependency]
    # ask_human_for_help],
)
def try_plan_to_make_progress (prev_working_code: str, test_project_page: str, prev_log: str) -> str : ... # returns the modified code

#def eval_plan_to_make_progress_valid


class Question(BaseModel):
    question: str
    answer: str

def mock_input (ask : str, reply: str):
    print (ask)
    print (reply + "\n")
    return reply

print("""
Welcome to Paketerix, your friendly Nix packaging assistant.
For now the only supported functionality is
* packaging projects which are on GitHub,
* which are sensible to build using mkDerivation and
* list their dependencies in the README.md (TODO: update this so it's accurate)
""")
project_url = mock_input("Enter the Github URL of the project you would like to package:\n", "https://github.com/bigbigmdm/IMSProg") #  "https://github.com/docker/compose")
assert (project_url.startswith("https://github.com/"))

project_page = scrape_and_process(project_url)

print ("I found the following information on the project page:\n")
print (project_page)

model_reply = try_plan_to_make_progress(starting_template, project_page, None)
print ("model reply:\n" + model_reply)

updated_code = extract_updated_code(model_reply)
print ("updated code:\n" + updated_code)

flake = init_flake()
update_flake(flake, updated_code)

result = invoke_build(flake.name)

print (f"{result.returncode}:{result.stderr}")

input("Wait for input")
