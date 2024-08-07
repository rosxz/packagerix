from pydantic import BaseModel
from magentic import prompt, prompt_chain
import os
import config
import litellm
from typing import Optional

config.init()

from app.nix import *
from app.flake import *
from app.parsing import *

# loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
# openai_loggers = [logger for logger in loggers if logger.name.startswith("openai")]
# logging.getLogger("openai._base_client").setLevel(logging.DEBUG)

os.environ["ANTHROPIC_API_KEY"] = secret_keys.anthropic_api
os.environ["OPENAI_API_KEY"] = secret_keys.openai_api

#litellm.set_verbose=True

# Function calling is not supported by anthropic. To add it to the prompt, set
litellm.add_function_to_prompt = True

def package_missing_dependency (name: str): pass
    # itentify source
    # recurse into original process
    #   - init new git template
    #   - read github repo
    #   - everything


def fix_dummy_hash (error_message: str): ...
    # not sure if I should do this with an LLM first
    # or do it manually right away


class Project(BaseModel):
    name: str
    latest_commit_sha1: str
    version_tag : Optional[str]
    dependencies: list[str]

@prompt("""
You are software packaging expert who can build any project using the Nix programming language.
           
Read the contents of the project's GitHub page and return a Project object with the grathered information.

Here is the project's GitHub page:

```text
{project_page}
```
""")
def gather_project_info (project_page: str) -> Project : ...


@prompt("""
You are software packaging expert who can build any project using the Nix programming language.

Read the contents of the project's GitHub page and fill out all of the sections in the code template that are marked with ... .
Do not make any other modifications. Do not modify lib.fakeHash.

Your goal is to make the build progress further, but without adding any unnecessary configuration or dependencies.

This is the code template you have to fill out:

```nix
{code_template}
```   

Here is the information form the project's GitHub page:

```text
{project_page}
```

Note: your reply should contain exaclty one code block with the updated Nix code.
""")
def set_up_project (code_template: str, project_page: str) -> str : ...

@prompt_chain("""
You are software packaging expert who can build any project.
Your goal is to make the build of your designated progress proceed one step further.

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
#model_reply = gather_project_info(project_page)
model_reply = set_up_project(starting_template, project_page)
print ("model reply:\n" + model_reply)
code = extract_updated_code(model_reply)
test_updated_code(code)

input("Wait for input")
