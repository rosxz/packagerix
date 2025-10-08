"""Module defining the Solution data model."""
from pydantic import BaseModel
from vibenix.errors import NixBuildResult

class Solution(BaseModel):
    """Represents a solution candidate with its code and build result."""
    code: str
    result: NixBuildResult
