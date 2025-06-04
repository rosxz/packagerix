"""Functions and code snippets for potential future additions to paketerix."""

from pydantic import BaseModel


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