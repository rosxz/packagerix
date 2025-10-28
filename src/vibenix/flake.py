import shutil
import os
import git

from vibenix import config
from vibenix.ui.logging_config import logger


def init_flake():

    logger.info(f"Creating flake at {config.flake_dir} from reference directory {config.template_dir}")
    
    def ignore_problematic_symlinks(src, names):
        """Ignore 'result' directories and other problematic symlinks that could cause infinite loops."""
        ignored = []
        for name in names:
            src_path = os.path.join(src, name)
            if name == 'result' or (os.path.islink(src_path) and not os.path.exists(src_path)):
                ignored.append(name)
        return ignored
    
    shutil.copytree(config.template_dir, config.flake_dir, dirs_exist_ok=True, ignore=ignore_problematic_symlinks)

    # Ensure the directory and all files have proper permissions
    os.chmod(config.flake_dir, 0o755)
    for root, dirs, files in os.walk(config.flake_dir):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)

    repo = git.Repo.init(config.flake_dir.as_posix())
    repo.git.add('-A')
    repo.index.commit("add empty template")

def update_flake(new_content, do_commit: bool = False) -> str:
    file_path = config.flake_dir / "package.nix"

    # Open the file in write mode and overwrite it with new_content
    with open(file_path, 'w') as file:
        file.write(new_content)

    repo = git.Repo(config.flake_dir.as_posix())
    if not do_commit:
        return None
    repo.git.add('-A')
    commit = repo.index.commit("build step")
    return commit.hexsha

def get_package_contents() -> str:
    file_path = config.flake_dir / "package.nix"
    with open(file_path, 'r') as file:
        return file.read()

def get_package_path() -> str:
    file_path = config.flake_dir / "package.nix"
    return file_path.as_posix()

def revert_to_commit(commit_hash: str) -> None:
    """
    Revert the packaging files to a previous commit.
    Used to sync package.nix with the best known solution during rollbacks.
    
    Args:
        commit_hash: The commit hash to revert to
    """
    repo = git.Repo(config.flake_dir.as_posix())
    repo.git.reset('--hard', commit_hash)
