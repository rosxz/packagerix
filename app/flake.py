import shutil
import os
import git

from app.config import flake_dir, template_dir


def init_flake():

    print(f"creating flake at {flake_dir} from reference directory {template_dir}", )
    shutil.copytree(template_dir, flake_dir, dirs_exist_ok = True)

    repo = git.Repo.init(flake_dir.as_posix())
    repo.git.add('-A')
    repo.index.commit("add empty template")

def update_flake(new_content):
    file_path = flake_dir / "package.nix"

    # Open the file in write mode and overwrite it with new_content
    with open(file_path, 'w') as file:
        file.write(new_content)

    repo = git.Repo(flake_dir.as_posix())
    repo.git.add('-A')
    repo.index.commit("build step")

# @prompt("""
# determine if the two truncated build logs contain the same error
# Log 1:
# ```
# {log1_tail}
# ```

# Log 2:
# ```
# {log2_tail}
# ```
# """)
def same_build_error(log1_tail: str, log2_tail : str)  -> bool : ...
# consider asking for human intervention to break tie   

# distinguish nix build errors from nix eval errors
# by looking for "nix log" sring and other markers
def is_eval_error() -> bool : ...
