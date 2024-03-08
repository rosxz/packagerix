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
def same_build_error(log1_tail: str, log2_tail : str)  -> Bool : ...
# consider asking for human intervention to break tie   

# distinguish nix build errors from nix eval errors
# by looking for "nix log" sring and other markers
def is_eval_error() -> : ...


# read build log of previous step and this step
# to evalute if the model made progress towards building the project
# this is done by counting magical phrases in the build output like
# "comiling ..." 
# a significantly higher number of magical phrases indicates progress
# an about equal amount goes to an llm to break the tie using same_build_error with the two tails of the two build logs
def eval_progress() -> Bool : ...

template : str = """
{
fetchFromFithub
}: {

src = fetchFromGithub()

}
"""

def build_package(source : str) -> Bool : ...

def invoke_build(sourse: str) -> Bool : ...

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

@prompt("Generate {num} quiz questions about {topic}")
def generate_questions(topic: str, num: int) -> list[Question]: ...


@prompt(
    """Return true if the user's answer is correct.
Question: {question.question}
Answer: {question.answer}
User Answer: {user_answer}"""
)
def is_answer_correct(question: Question, user_answer: str) -> bool: ...


@prompt(
    "Create a short and funny message of celebration or encouragment for someone who"
    " scored {score}/100 on a quiz about {topic}."
)
def create_encouragement_message(score: int, topic: str) -> str: ...

# get repo you want packaged

# prepare adequate template

# invoke bulid_package()




topic = input("Enter a topic for a quiz: ")
num_questions = int(input("Enter the number of questions: "))
questions = generate_questions(topic, num_questions)

user_points = 0
for num, question in enumerate(questions, start=1):
    print(f"\n{num} / {len(questions)}")
    print(f"Q: {question.question}")
    user_answer = input("A: ")

    if is_answer_correct(question, user_answer):
        print(f"Correct! The answer is: {question.answer}")
        user_points += 1
    else:
        print(f"Incorrect! The correct answer is: {question.answer}")

score = 100 * user_points // len(questions)
print(f"\nQuiz complete! You scored: {score}%\n")
print(create_encouragement_message(score, topic))
