"""Search for packages that provide specific files using nix-locate."""

from vibenix.ccl_log import get_logger, log_function_call
from vibenix.tools.nix_locate_tool import nix_locate_for_llm

@log_function_call("search_nixpkgs_for_file")
def search_nixpkgs_for_file(file_path: str, regex: bool = False, exact_match: bool = False) -> str:
    """
    Find packages in nixpkgs that provide a specific file path (using nix-locate).
    
    Args:
        file_path: The file path to search for (e.g., "bin/gcc", "lib/libz.so", "/usr/share/man/man1/gcc.1")
        regex: If True, treat file_path as a regular expression (e.g., "bin/.*cc$", "lib/.*\\.so\\.1")
        exact_match: If True, only match files with exact basename (e.g., "bin/gcc" won't match "bin/gcc-12")
        
    Returns:
        A Nix attribute set with packages that provide the file, formatted as:
        {
          direct_matches = [
            "${pkgs.gcc}/bin/gcc"
            "${pkgs.clang}/bin/gcc"
          ];
          symlink_matches = [
            "${pkgs.somePackage}/bin/gcc"
          ];
        }
        
    The symlink_matches list contains packages where the file is not contained directly, but reachable through symlinks (indirect matches).
    """

    return nix_locate_for_llm(file_path, regex=regex, exact_match=exact_match)