# https://github.com/jackmpcollins/magentic

from pydantic import BaseModel

from magentic import prompt_chain

from pathlib import Path

import os

import logging

import config

config.init()

loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
openai_loggers = [logger for logger in loggers if logger.name.startswith("openai")]
logging.getLogger("openai._base_client").setLevel(logging.DEBUG)

os.environ["ANTHROPIC_API_KEY"] = "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"
os.environ["OPENAI_API_KEY"] = "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"

import litellm

from app.nix import *
from app.flake import *
from app.parsing import *

#litellm.set_verbose=True

# Function calling is not supported by anthropic. To add it to the prompt, set
#litellm.add_function_to_prompt = True #.
#litellm.drop_params=True

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


@prompt_chain("""
You are software packaging expert who can build any project.
   
Read the contents of the project's GitHub page and fill out all of the sections in the code that are marked with ... .

Your goal is to make the build progress further, but without adding any unnecessary configuration or dependencies.

This is the code template you have to fill out:

```nix
{prev_working_code}
```   

Here is the information form the projects github page:

```text
{test_project_page}
```

Note: do not modify lib.fakeHash.     
""",
functions=[test_updated_code] # search_nixpkgs_for_package]
    # package_missing_dependency, ask_human_for_help],
)
def build_project (prev_working_code: str, test_project_page: str) -> str : ... # returns the modified code

@prompt_chain("""
You are software packaging expert who can build any project.
   
First you will read the contents of the project's GitHub page.

You will use the information from the GitHub page to identify dependencis and fill out all of the sections in the code that are marked with ... .
Then you will attempt to build the project for the fist time.

Subsequently you will go through the following steps in a loop
1. look at the error from the previous build
2. identify the missing dependency indicated by the error (use tools to get more information if requrired) and
3. add the dependency indicated by the error to the next build.

Your goal is to make the build progress further with each ste without adding any unnecessary configuration or dependencies.

This is the template where you have to initially fill in the ... .

```nix
{prev_working_code}
```   

Here is the information form the projects github page to get started:

```text
{test_project_page}
```

Note: sha-256 hashes are filled in by invoking the build with lib.fakeHash and obtaining the correct sha256 from the build output.
Note: always invoke the test_updated_code with updated code until the build succeeds              
""",
functions=[test_updated_code] # search_nixpkgs_for_package]
    # package_missing_dependency, ask_human_for_help],
)
def build_project (prev_working_code: str, test_project_page: str) -> str : ... # returns the modified code

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

flake = init_flake()
print (f"Working on temporary flake at {flake_dir}")

starting_template = (config.template_dir / "package.nix").read_text()
result = invoke_build()
error_stack.append(result)
model_reply = build_project(starting_template, project_page)
print ("model reply:\n" + model_reply)

input("Wait for input")
