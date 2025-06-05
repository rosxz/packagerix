import shutil
import os
import git

from app.config import flake_dir, template_dir
from app.ui.logging_config import logger


def init_flake():

    logger.info(f"Creating flake at {flake_dir} from reference directory {template_dir}")
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

