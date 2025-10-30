"""Import all tool functions for use in the application."""

# Import search functions from their individual modules
from vibenix.tools.search_nixpkgs_literal import search_nixpkgs_for_package_literal
from vibenix.tools.search_nixpkgs_semantic import search_nixpkgs_for_package_semantic
from vibenix.tools.search_nix_functions import search_nix_functions
from vibenix.tools.search_nixpkgs_file import search_nixpkgs_for_file
from vibenix.tools.search_nixpkgs_manual_documentation import search_nixpkgs_manual_documentation
from vibenix.tools.str_replace import str_replace
from vibenix.tools.view import view
from vibenix.tools.insert import insert_line_after
from vibenix.tools.error_pagination import error_pagination
from vibenix.tools.build_package import build_package

# Export all functions so they can be imported from this module
__all__ = [
    'search_nixpkgs_for_package_literal',
    'search_nixpkgs_for_package_semantic',
    'search_nix_functions',
    'search_nixpkgs_for_file',
    'search_nixpkgs_manual_documentation',
    'str_replace',
    'insert_line_after',
    'view',
    'error_pagination',
    'build_package',
]
