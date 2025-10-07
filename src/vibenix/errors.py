"""Error types for the vibenix build system."""

from enum import Enum
from pydantic import BaseModel
from typing import Optional

class NixBuildErrorDiff(Enum):
    REGRESS = "REGRESS"
    PROGRESS = "PROGRESS"
    STAGNATION = "STAGNATION"
    BROKEN_LOG_OUTPUT = "BROKEN_LOG_OUTPUT"

class NixErrorKind(Enum):
    EVAL_ERROR = "EVAL_ERROR"
    BUILD_ERROR = "BUILD_ERROR"
    INVALID_HASH = "INVALID_HASH"
    HASH_MISMATCH = "HASH_MISMATCH"
    DEPENDENCY_BUILD_ERROR = "DEPENDENCY_BUILD_ERROR"

class NixError(BaseModel):
    type: NixErrorKind
    error_message: str
    
    def truncated(self, max_lines: int = 256) -> str:
        """Return truncated version of error message, keeping the tail end.
        
        Args:
            max_lines: Maximum number of lines to include from the end
            
        Returns:
            Truncated error message showing the last N lines
        """
        lines = self.error_message.split('\n')
        
        if len(lines) <= max_lines:
            return self.error_message
        
        truncated_lines = lines[-max_lines:]
        truncated = f"... ({len(lines) - max_lines} lines omitted) ...\n\n"
        truncated += '\n'.join(truncated_lines)
        
        return truncated


class NixBuildResult(BaseModel):
    """Result of a Nix build operation."""
    success: bool
    is_src_attr_only: bool
    error: Optional[NixError] = None


class FullLogDiff(BaseModel):
    """Log comparison showing full logs (when both are under 100 lines)."""
    previous_log: str
    new_log: str
    initial_lines: int
    improvement_lines: int


class ProcessedLogDiff(BaseModel):
    """Log comparison showing truncated logs with divergence analysis."""
    previous_log_truncated: str
    new_log_truncated: str
    initial_lines: int
    improvement_lines: int
    divergence_line: int


LogDiff = FullLogDiff | ProcessedLogDiff
