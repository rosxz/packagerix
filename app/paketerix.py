from pydantic import BaseModel
from magentic import prompt, prompt_chain, StreamedStr
from magentic import (
    chatprompt,
    AssistantMessage,
    FunctionCall,
    FunctionResultMessage,
    UserMessage,
    SystemMessage
)

import os
from app.logging_config import logger  # Import logger first to ensure it's initialized
from app import config
import litellm
from typing import Optional
from app import secret_keys

config.init()

from app.nix import *
from app.flake import *
from app.parsing import *

# loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
# openai_loggers = [logger for logger in loggers if logger.name.startswith("openai")]
# logging.getLogger("openai._base_client").setLevel(logging.DEBUG)

os.environ["ANTHROPIC_API_KEY"] = secret_keys.anthropic_api
os.environ["OPENAI_API_KEY"] = secret_keys.openai_api

import logging
if "OLLAMA_HOST" in os.environ:
    logger.info(f"OLLAMA_HOST is set to: {os.environ['OLLAMA_HOST']}")
else:
    logger.warning("OLLAMA_HOST environment variable is not set")

#litellm.set_verbose=True
# litellm.set_verbose=True

# Explicitly set ollama_api_base if OLLAMA_HOST is set
if "OLLAMA_HOST" in os.environ:
    litellm.api_base = os.environ["OLLAMA_HOST"]
    logger.info(f"Set litellm.api_base to: {litellm.api_base}")

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

@cache.memoize()
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

@prompt("""
You are software packaging expert who can build any project using the Nix programming language.

Read the contents of the project's GitHub page and return the following information.
    1. The build tool which should be invoked to build the project.
    2. A list of build tools and project dependencies.
    3. A list of other information which might be necessary for buiding the project.
""")
def identify_dependencies (code_template: str, project_page: str) -> str : ...

@prompt("""
You are software packaging expert who can build any project using the Nix programming language.

Read the contents of the project's GitHub page and summarize it.
Include information like
    1. The build tool which should be invoked to build the project.
    2. A list of build tools and project dependencies.
    3. Other information which might be necessary for buiding the project.
    
    Do not include information which is irrelevant for building the project.
Here is the information form the project's GitHub page:

```text
{project_page}
```
""")
def summarize_github (project_page: str) -> str : ...

#def eval_plan_to_make_progress_valid


class Question(BaseModel):
    question: str
    answer: str

def mock_input (ask : str, reply: str):
    logger.info(ask)
    logger.info(reply + "\n")
    return reply

def main():
    """Main function for the original CLI interface."""
    # Enable console logging for CLI mode
    from app.logging_config import enable_console_logging
    enable_console_logging()
    
    logger.info("""
Welcome to Paketerix, your friendly Nix packaging assistant.
For now the only supported functionality is
* packaging projects which are on GitHub,
* which are sensible to build using mkDerivation and
* list their dependencies in the README.md (TODO: update this so it's accurate)
""")
    project_url = mock_input("Enter the Github URL of the project you would like to package:\n", "https://github.com/bigbigmdm/IMSProg") #  "https://github.com/docker/compose")
    assert (project_url.startswith("https://github.com/"))

    project_page = scrape_and_process(project_url)

    logger.info("I found the following information on the project page:\n")
    logger.info(project_page)

    flake = init_flake()
    logger.info(f"Working on temporary flake at {flake_dir}")

    starting_template = (config.template_dir / "package.nix").read_text()
    starting_template_error = invoke_build()
    starting_template_error_for_func = Error(type=Error.ErrorType.EVAL_ERROR, error_message=get_last_ten_lines(starting_template_error.stderr))
    error_stack.append(starting_template_error)

    logger.info("Template:")
    logger.info(starting_template_error_for_func.model_dump_json())

    starting_template_call = FunctionCall(test_updated_code, starting_template)

    #model_reply = gather_project_info(project_page)
    model_reply = set_up_project(starting_template, project_page)
    logger.info("model reply:\n" + model_reply)
    code = extract_updated_code(model_reply)
    error = test_updated_code(code)
    error_trunc = error.error_message

    first_update_call = FunctionCall(test_updated_code, code)

    @chatprompt(
    SystemMessage(
    """
    You are software packaging expert who can build any project using the nix programming language.
    Your goal is to make the build of your designated progress proceed one step further.

    You will go through the following steps in a loop
    1. look at the current build error
    2. identify its cause, taking into account
        a) your previous changs
        b) potentially missing dependencies
    3. call the test_updated_code (again) to see if your change fixes the error

    Your goal is to make the build progress further with each ste without adding any unnecessary configuration or dependencies.

    Note: sha-256 hashes are filled in by invoking the build with lib.fakeHash and obtaining the correct sha256 from the build output.
    Note: Call the test_updated_code function repeatedly with updated code until the build succeeds. Do not respond directly.
    """),
    UserMessage("""
    Make this project build, step by step:
    ¸¸¸
    {template_str}
    ¸¸¸
    """),
    AssistantMessage(starting_template_call),
    FunctionResultMessage(starting_template_error_for_func, starting_template_call),
    AssistantMessage(first_update_call),
    FunctionResultMessage(error, first_update_call),
    functions=[test_updated_code] # search_nixpkgs_for_package]
        # package_missing_dependency, ask_human_for_help],
    )
    def build_project_inner (template_str) -> StreamedStr : ... # FunctionCall[Optional[Error]] : ... # returns the modified code

    #build_output = build_project_inner(starting_template)
    #logger.info(build_output)
    #build_output()
    #for chunk in build_project_inner(starting_template):
    #    logger.info(chunk)
    summary = summarize_github(project_page)
    logger.info(summary)
    input("\nend of output - waiting for keypress")


def build_project (template_str) -> StreamedStr : ... # Placeholder for external access


if __name__ == "__main__":
    main()
