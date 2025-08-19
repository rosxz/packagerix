"""Search for related packages in nixpkgs based on template type and project dependencies."""

import os
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from abc import ABC, abstractmethod
from typing import List, Set, Dict, Any
from vibenix.template.template_types import TemplateType
from vibenix.ccl_log import get_logger, log_function_call

# TODO add package set attribute to PackageType (a single package set, the most generic, is enough)
# TODO use the dependency_files attribute to search in project source for each depedency file (they might be in subdirectories after all), return the relative path to project source root for each found. This should be complementary to the model looking at the source code and project page to find stuff in the README and etc, not a replacement

class PackageType(ABC):
    """Abstract base class for package types with their builders and dependency files."""
    
    @property
    @abstractmethod
    def builders(self) -> List[str]:
        """List of Nix builders used by this package type."""
        pass
    
    @property
    @abstractmethod
    def dependency_files(self) -> List[str]:
        """List of dependency files to search for in the project source."""
        pass
    
    @property
    @abstractmethod
    def package_set(self) -> str:
        """The most generic package set for this package type."""
        pass


class RustPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["buildRustPackage"]
    
    @property
    def dependency_files(self) -> List[str]:
        return ["Cargo.toml", "Cargo.lock"]
    
    @property
    def package_set(self) -> str:
        return ""


class PythonPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["buildPythonPackage", "buildPythonApplication"]
    
    @property
    def dependency_files(self) -> List[str]:
        return ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "poetry.lock", "uv.lock"]
    
    @property
    def package_set(self) -> str:
        return "python3Packages"


class GoPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["buildGoModule", "buildGo"]
    
    @property
    def dependency_files(self) -> List[str]:
        return ["go.mod", "go.sum"]
    
    @property
    def package_set(self) -> str:
        return ""


class NpmPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["buildNpmPackage", "nodePackages"]
    
    @property
    def dependency_files(self) -> List[str]:
        return ["package.json", "package-lock.json", "yarn.lock"]
    
    @property
    def package_set(self) -> str:
        return "nodePackages"


class DartPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["buildDartApplication"]
    
    @property
    def dependency_files(self) -> List[str]:
        return ["pubspec.yaml", "pubspec.lock"]
    
    @property
    def package_set(self) -> str:
        return ""


class FlutterPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["buildFlutterApplication"]
    
    @property
    def dependency_files(self) -> List[str]:
        return ["pubspec.yaml", "pubspec.lock"]
    
    @property
    def package_set(self) -> str:
        return ""


class ZigPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["buildZigPackage"]
    
    @property
    def dependency_files(self) -> List[str]:
        return ["build.zig", "build.zig.zon"]
    
    @property
    def package_set(self) -> str:
        return ""


class GenericPackageType(PackageType):
    @property
    def builders(self) -> List[str]:
        return ["mkDerivation"] #, "cmake", "meson", "autotools"
    
    @property
    def dependency_files(self) -> List[str]:
        return ["CMakeLists.txt", "Makefile", "configure.ac", "meson.build", "Makefile.am"]
    
    @property
    def package_set(self) -> str:
        return ""


def find_dependency_files_in_project(package_type: PackageType, project_search_file_func: Any) -> List[str]:
    """Find dependency files in the project source using the package type's dependency_files.
    
    Args:
        package_type: The package type with dependency_files to search for
        project_search_file_func: Function to search for files in project (search_for_file from file_tools)
    
    Returns:
        List of relative paths to found dependency files
    """
    found_files = []
    
    for dep_file in package_type.dependency_files:
        # Search for the dependency file in the project source using search_for_file
        search_result = project_search_file_func(dep_file, ".")
        
        if "Error" not in search_result and "No matches" not in search_result:
            # The result contains file paths, one per line
            for line in search_result.strip().split('\n'):
                filepath = line.strip()
                if filepath and filepath not in found_files:
                    found_files.append(filepath)
    
    return found_files


TEMPLATE_TO_PACKAGE_TYPE: Dict[TemplateType, PackageType] = {
    TemplateType.RUST: RustPackageType(),
    TemplateType.PYTHON: PythonPackageType(),
    TemplateType.PYTHON_UV: PythonPackageType(),
    TemplateType.GO: GoPackageType(),
    TemplateType.NPM: NpmPackageType(),
    TemplateType.PNPM: NpmPackageType(),
    TemplateType.DART: DartPackageType(),
    TemplateType.FLUTTER: FlutterPackageType(),
    TemplateType.ZIG: ZigPackageType(),
    TemplateType.GENERIC: GenericPackageType(),
}


@log_function_call("search_related_packages")
def search_related_packages(template_type: TemplateType, nixpkgs_search_func: Any, project_page: str, dependencies: str = None) -> str:
    """Search for related packages in nixpkgs using semantic similarity, filtered by builder type.
    
    Args:
        template_type: The template type for the project
        nixpkgs_search_func: Function to search in nixpkgs files (from file_tools)
        project_page: Content of the project page (e.g., README.md)
        dependencies: List of project dependencies to help find related packages
    
    Returns:
        A formatted string with semantically similar packages that use the same builders
    """
    print(f"📞 Function called: search_related_packages for template: {template_type.value}")
    
    package_type = TEMPLATE_TO_PACKAGE_TYPE.get(template_type, GenericPackageType())
    
    # Get path to pre-computed embeddings
    embeddings_path = os.environ.get('NIXPKGS_EMBEDDINGS')
    if not embeddings_path:
        return "Error: NIXPKGS_EMBEDDINGS environment variable not set. Please run from nix develop shell."
    
    if not os.path.exists(embeddings_path):
        return f"Error: Pre-computed embeddings not found at {embeddings_path}"
    
    # Load pre-computed embeddings
    try:
        with open(embeddings_path, 'rb') as f:
            data = pickle.load(f)
            embeddings = data['embeddings']
            package_names = data['names']
            packages = data['packages']
    except Exception as e:
        return f"Error loading pre-computed embeddings: {str(e)}"
    
    # Create project embedding from project page + dependencies
    # Handle dependencies as either string or list
    if isinstance(dependencies, str):
        dependencies_text = f"Dependencies: {dependencies}" if dependencies else ""
        dependencies_list = [dep.strip() for dep in dependencies.split('\n') if dep.strip() and not dep.strip().startswith('#')]
    elif isinstance(dependencies, list):
        dependencies_list = dependencies
        dependencies_text = f"Dependencies: {', '.join(dependencies)}" if dependencies else ""
    else:
        dependencies_list = []
        dependencies_text = ""
    
    project_text = f"{project_page}\n{dependencies_text}"
    
    # Load model and encode project text
    model = SentenceTransformer('all-MiniLM-L6-v2')
    project_embedding = model.encode([project_text])
    
    # Calculate similarities with all packages
    similarities = cosine_similarity(project_embedding, embeddings)[0]
    
    # Get top semantic matches first
    top_indices = np.argsort(similarities)[::-1][:200]  # Top 200 semantic matches
    
    # Filter matches to only include packages that use the same builders
    filtered_matches = []
    package_dict = {entry['key']: entry['value'] for entry in packages}
    
    for idx in top_indices:
        if similarities[idx] < 0.2:  # Skip very low similarity scores
            break
            
        pkg_name = package_names[idx]
        pkg_info = package_dict.get(pkg_name, {})
        
        # Check if this package uses any of our builders by searching its file content
        uses_builder = False
        for builder in package_type.builders:
            # Search for the builder in nixpkgs files containing this package
            search_result = nixpkgs_search_func(builder, ".", f"--files-with-matches --glob '*{pkg_name}*'")
            if "Error" not in search_result and "No matches" not in search_result and search_result.strip():
                uses_builder = True
                break
        
        if uses_builder:
            filtered_matches.append({
                'name': pkg_name,
                'version': pkg_info.get('version', ''),
                'description': pkg_info.get('description', ''),
                'score': similarities[idx]
            })
            
            # Stop once we have enough matches
            if len(filtered_matches) >= 5:
                break
    
    # Format results
    result_lines = [
        f"# Semantically similar packages for {template_type.value} template",
        f"# Builders: {', '.join(package_type.builders)}",
        f"# Dependencies used for ranking: {', '.join(dependencies_list) if dependencies_list else 'None'}",
        f"# Found {len(filtered_matches)} semantically similar packages with matching builders",
        ""
    ]
    
    if filtered_matches:
        result_lines.append("## Most semantically similar packages (same builders):")
        for i, match in enumerate(filtered_matches[:5]):
            score_pct = match['score'] * 100
            result_lines.append(f"  {i+1}. {match['name']} (similarity: {score_pct:.1f}%)")
            if match['description']:
                desc = match['description'][:100] + "..." if len(match['description']) > 100 else match['description']
                result_lines.append(f"     Description: {desc}")
            result_lines.append("")
    else:
        result_lines.append("No semantically similar packages found with matching builders.")
    
    return '\n'.join(result_lines)

@log_function_call("get_dependency_files")
def get_dependency_files(template_type: TemplateType, project_search_file_func: Any = None) -> List[str]:
    """Find common dependency files in the project source.
    
    Args:
        template_type: The template type for the project
        project_search_file_func: Function to search for files in project
    
    Returns:
        A formatted string with related packages found in nixpkgs
    """
    print(f"📞 Function called: search_related_packages for template: {template_type.value}")

    package_type = TEMPLATE_TO_PACKAGE_TYPE.get(template_type, GenericPackageType())

    found_dependency_files = []
    if project_search_file_func:
        found_dependency_files = find_dependency_files_in_project(package_type, project_search_file_func)

    return found_dependency_files
