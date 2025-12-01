import os
import atexit
from pathlib import Path
import tempfile
from collections import deque
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from vibenix.packaging_flow.Solution import Solution
    #from vibenix.errors import NixBuildResult

solution_stack: List['Solution']
build_timeout: str

def init():
    global solution_stack
    solution_stack = []

    global template_dir

    script_dir = os.path.dirname(os.path.abspath(__file__))
    reference_directory_name = 'template'
    template_dir = Path(script_dir, reference_directory_name)

    global flake_dir

    flake_dir_obj = tempfile.TemporaryDirectory()
    #atexit.register(flake_dir_obj.cleanup)

    flake_dir = Path(flake_dir_obj.name)
    # time out build after 7 minutes
    global build_timeout
    build_timeout = str(7*60)
   
