"""Tools to view and read the files present in the locally built package's out path."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.flake import get_package_contents

from vibenix.tools import file_tools
import functools


def create_out_path_file_tools():
    """
    Create all the file tools, but wrap them with a method that updates
    the root_dir variable of the class to the out_path of the last (successful)
    solution.
    """
    funcs = file_tools.create_source_function_calls(
        store_path="/tmp",
        prefix="out_path_",
        dynamic_path=True
    )
    funcs, update_path = funcs[:-1], funcs[-1]
    
    def decorate_with_out_path_update(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # TODO get out path from top solution from solution stack if it has it
            from vibenix import config
            out_path = config.solution_stack[-1].out_path
            if not out_path:
                raise RuntimeError("No out_path found in the latest solution to update file tools path.")
            update_path(out_path)
            result = func(*args, **kwargs)
            return result
        return wrapper

    decorated_funcs = [decorate_with_out_path_update(f) for f in funcs]
    for func in decorated_funcs:
        func.__doc__ = func.__doc__.replace("_source", "")
    return decorated_funcs
