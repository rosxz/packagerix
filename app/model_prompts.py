"""All model prompts for paketerix.

This module contains all functions decorated with @ask_model that interact with the AI model.
"""

from magentic import StreamedStr
from app.coordinator import ask_model
from app.nix import Error


@ask_model("""@model You are software packaging expert who can build any project using the Nix programming language.

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
def set_up_project(code_template: str, project_page: str) -> StreamedStr:
    """Initial setup of a Nix package from a GitHub project."""
    ...


@ask_model("""@model You are software packaging expert who can build any project using the Nix programming language.

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
def summarize_github(project_page: str) -> StreamedStr:
    """Summarize a GitHub project page for packaging purposes."""
    ...


@ask_model("""@model I'll fix this build error and try again.

Current code:
```nix
{code}
```

Error:
```
{error}
```

Please fix the code to resolve the error. Return only the updated Nix code.
""")
def fix_build_error(code: str, error: Error) -> StreamedStr:
    """Fix a build error in Nix code."""
    ...