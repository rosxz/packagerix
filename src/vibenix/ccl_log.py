"""
Structured logging in CCL (Categorical Configuration Language) format for Vibenix.

Based on: https://chshersh.com/blog/2025-01-06-the-most-elegant-configuration-language.html
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, TextIO
from dataclasses import dataclass, field
from contextlib import contextmanager

from .errors import NixBuildErrorDiff, NixBuildResult


@dataclass
class CCLLogger:
    """
       Logs events in CCL format.
       See: https://chshersh.com/blog/2025-01-06-the-most-elegant-configuration-language.html
    """
    
    log_file: Path
    _file_handle: TextIO = field(init=False)
    _current_indent: int = field(default=0, init=False)
    _start_time: float = field(init=False)
    
    def __post_init__(self):
        self._file_handle = open(self.log_file, 'w', buffering=1)
        self._start_time = time.time()
        self._write_header()
    
    def _write_header(self):
        """Write header with metadata."""
        # TODO: add things like model version and a commit hash
        self._write("start_time = " + datetime.now().isoformat(), 0)
        self._write("")
    
    def _elapsed_time(self) -> str:
        """Get elapsed time since start formatted as hh:mm:ss.mmm."""
        elapsed = time.time() - self._start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = elapsed % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    
    def close(self):
        """Close the log file."""
        self._file_handle.close()
    
    def _write(self, line: str, indent_level=None):
        """Write a line with current indentation."""
        if not indent_level:
            indent_level = self._current_indent
        self._file_handle.write("  " * indent_level + line + "\n")

    @contextmanager
    def _section_begin(self, section_head, indent_level):
        """Context manager for writing indented sections."""
        self._write(section_head, indent_level)
        self._current_indent = indent_level + 1
        yield
        self._current_indent = indent_level

    def _section_content(self, indent_level):
        """Context manager for writing indented sections."""
        prev_indent = self._current_indent
        self._current_indent = indent_level + 1
        yield
        self._current_indent = prev_indent + 1

    def log_session_start(self, project_url: str):
        """Log the start of a packaging session."""
        with self._section_begin("session-start =", 0):
            self._write("elapsed = " + self._elapsed_time())
            self._write("project_url = " + project_url)
    
    def log_session_end(self, success: bool, total_iterations: int, total_cost: float = None):
        """Log the end of a packaging session."""
        with self._section_begin("session-end =", 0):
            self._write("elapsed = " + self._elapsed_time())
            self._write("success = " + ("true" if success else "false"))
            self._write("total_iterations = " + str(total_iterations))
            if total_cost is not None:
                self._write(f"total_cost = {total_cost:.6f}")
    
    def log_template_selected(self, template: str):
        """Log template selection."""
        with self._section_begin("template-selected =", 0):
            self._write("event = selected")
            self._write("elapsed = " + self._elapsed_time())
            self._write("name = " + template)

    def log_initial_build(self, result: NixBuildResult):
        """Log the initial build result."""
        with self._section_begin("initial-build =", 0):
            if result.success:
                self._write("result = success")
            elif result.error:
                self._write("result = " + result.error.type.value)
            self._write("elapsed = " + self._elapsed_time())

    def log_before_iterations(self):
        """Log template selection."""
        self._write("iteration =", 0)
    
    def log_iteration_start(self, iteration: int):
        """Log the start of a build iteration."""
        self._write(f"= {iteration} =", 1)

    def log_iteration_end(self, iteration: int, output : NixBuildResult):
        """Log the end of a build iteration."""
        if output.success:
            self._write("type = success", 2)
        elif output.error:
            self._write("type = " + output.error.type.value, 2)
        self._write("elapsed = " + self._elapsed_time(), 2)

    def log_progress_eval(self, iteration: int, diff : NixBuildErrorDiff):
        """Log progress evaluation."""
        with self._section_begin("progress_eval =", 2):
            self._write("result = " + diff.value)
            self._write("elapsed = " + self._elapsed_time())
    
    
    def log_function_call(self, function_name: str, **kwargs):
        """Log a function call to the model."""
        with self._section_begin("function_call =", 2):
            self._write("elapsed = " + self._elapsed_time())
            self._write("name = " + function_name)
            for key, value in kwargs.items():
                self._write(f"{key} = {value}")
    
    def log_error(self, error_type: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an error with context."""
        with self._section_begin("error =", 0):
            self._write("elapsed = " + self._elapsed_time())
            self._write("type = " + error_type)
            self._write("message = " + message)
            if context:
                with self._section_begin("context =", 1):
                    for key, value in context.items():
                        self._write(f"{key} = {value}")


# Global logger instance
_logger: CCLLogger = None


def init_logger(log_file: Path) -> CCLLogger:
    """Initialize the global CCL logger."""
    global _logger
    _logger = CCLLogger(log_file=log_file)
    return _logger


def get_logger() -> CCLLogger:
    """Get the global CCL logger instance."""
    if _logger is None:
        raise RuntimeError("CCL logger not initialized. Call init_logger() first.")
    return _logger


def close_logger():
    """Close the global logger."""
    global _logger
    if _logger:
        _logger.close()
        _logger = None
