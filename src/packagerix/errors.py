"""Error types for the packagerix build system."""

from enum import Enum
from pydantic import BaseModel
from typing import Optional


class NixBuildErrorDiff(Enum):
    REGRESS = (1, "error not resolved - build fails earlier")
    PROGRESS = (2, "error resolved - build fails later")
    def __init__(self, id, description):
        self.id = id
        self.description = description

    @classmethod
    def from_id(cls, id):
        for case in cls:
            if case.id == id:
                return case
        raise ValueError(f"No case with id {id}")

class NixErrorKind(Enum):
    EVAL_ERROR = (2, "code failed to evaluate")
    BUILD_ERROR = (3, "code sucessfully evaluates, but build step fails")
    HASH_MISMATCH = (4, "hash mismatch - needs correct hash to be filled in")

    def __init__(self, id, description):
        self.id = id
        self.description = description

    @classmethod
    def from_id(cls, id):
        for case in cls:
            if case.id == id:
                return case
        raise ValueError(f"No case with id {id}")

class NixError(BaseModel):
    type: NixErrorKind
    error_message: str


class NixBuildResult(BaseModel):
    """Result of a Nix build operation."""
    success: bool
    error: Optional[NixError] = None