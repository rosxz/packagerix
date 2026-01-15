from pydantic import BaseModel

class RefinementIterationResult(BaseModel):
    """Result of a single refinement iteration, concisely detailing the tasks identified and the lessons learned to serve as reference for future iterations.
    Args:
        tasks_identified (list[str]): List of tasks identified during this iteration.
        lessons_learned (list[str]): List of additional lessons learned during this iteration.
    Example:
        tasks_identified = ["Add missing dependencies X and Y, identified by running package executable with `package --version`."]
        lessons_learned = ["Dependency Z is broken and should not be used.", "Package is an executable that needs to be wrapped."]
    """
    tasks_identified: list[str] = []
    lessons_learned: list[str] = []

    def __str__(self) -> str:
        result = "Refinement Iteration Result:\n"
        result += "Tasks Identified:\n"
        for task in self.tasks_identified:
            result += f"- {task}\n"
        result += "Lessons Learned:\n"
        for lesson in self.lessons_learned:
            result += f"- {lesson}\n"
        return result
        
class IterationResult(BaseModel):
    """Result of a single coding iteration, concisely describing the tasks performed.
    Args:
        tasks_performed (list[str]): List of tasks performed during the iteration.
    Example:
        tasks_performed = ["Added missing dependencies X and Y.", "Changed Nix builder to W."]
    """
    tasks_performed: list[str] = []
    
    def __str__(self) -> str:
        result = "Tasks Performed:\n"
        for task in self.tasks_performed:
            result += f"- {task}\n"
        return result

