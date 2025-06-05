"""Functions and code snippets for potential future additions to paketerix."""

from pydantic import BaseModel

@prompt("""
You are software packaging expert who can build any project using the Nix programming language.

Read the contents of the project's GitHub page and return the following information.
    1. The build tool which should be invoked to build the project.
    2. A list of build tools and project dependencies.
    3. A list of other information which might be necessary for buiding the project.
""")
def identify_dependencies (code_template: str, project_page: str) -> str : ...

def package_missing_dependency(name: str):
    pass
    # itentify source
    # recurse into original process
    #   - init new git template
    #   - read github repo
    #   - everything


def fix_dummy_hash(error_message: str):
    ...
    # not sure if I should do this with an LLM first
    # or do it manually right away


class Question(BaseModel):
    question: str
    answer: str


def build_project(template_str) -> str:
    ... # Placeholder for external access


# Commented out code from main():
# build_output = build_project_inner(starting_template)
# logger.info(build_output)
# build_output()
# for chunk in build_project_inner(starting_template):
#     logger.info(chunk)