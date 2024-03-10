# https://github.com/jackmpcollins/magentic

from pydantic import BaseModel

from magentic import prompt


@prompt("""
determine if the two truncated build logs contain the same error
Log 1:
```
{log1_tail}
```

Log 2:
```
{log2_tail}
```
""")
def same_build_error(log1_tail: str, log2_tail : str)  -> bool : ...
# consider asking for human intervention to break tie   

# distinguish nix build errors from nix eval errors
# by looking for "nix log" sring and other markers
def is_eval_error() -> bool : ...


# read build log of previous step and this step
# to evalute if the model made progress towards building the project
# this is done by counting magical phrases in the build output like
# "comiling ..." 
# a significantly higher number of magical phrases indicates progress
# an about equal amount goes to an llm to break the tie using same_build_error with the two tails of the two build logs
def eval_progress() -> bool : ...

template : str = """
{
fetchFromFithub
}: {

src = fetchFromGithub()

}
"""

def build_package(source : str) -> bool : ...

def invoke_build(sourse: str) -> bool : ...

def eval_build(source: str, prev_log: str) -> str : ...


@prompt("""
Make a targeted and incremental addition to the existing Nix derivation so that the build progesses further.
This is the code you are starting from:

{prev_working_code}
""",
#functions=[eval_build, ask_human_for_help],
)
def try_plan_to_make_progress (prev_working_code: str, prev_log: str) -> str : ... # returns the modified code

#def eval_plan_to_make_progress_valid


class Question(BaseModel):
    question: str
    answer: str


# get repo you want packaged

# prepare adequate template

# invoke bulid_package()

project = input("Enter the URL of the project you would like to package")
num_questions = int(input("Enter a number: "))
package = try_plan_to_make_progress("", project)

print(f"\n{package}%\n")
