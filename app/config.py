import os
import atexit
from pathlib import Path
import tempfile
from collections import deque

def init():
    global error_stack
    error_stack = []

    global template_dir

    script_dir = os.path.dirname(os.path.abspath(__file__))
    reference_directory_name = '../template'
    template_dir = Path(script_dir, reference_directory_name)

    global flake_dir

    flake_dir_obj = tempfile.TemporaryDirectory()
    atexit.register(flake_dir_obj.cleanup)

    flake_dir = Path(flake_dir_obj.name)
   