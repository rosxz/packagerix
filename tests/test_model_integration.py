"""Integration tests where the model actually calls the function tools."""

import pytest
from magentic import prompt_chain
from packagerix.function_calls import search_nixpkgs_for_package, web_search, fetch_url_content, search_nix_functions


def print_model_response(response: str, request) -> str:
    """Utility function to print model responses for debugging."""
    test_name = request.node.name
    print(f"\n=== MODEL RESPONSE for {test_name} ===")
    print(response)
    print(f"=== END MODEL RESPONSE ===\n")
    return response


# Define prompt_chain functions outside of class to avoid self parameter conflicts
@prompt_chain(
    "Search for a package called {package_name} in nixpkgs and tell me what you found.",
    functions=[search_nixpkgs_for_package],
)
def search_and_describe_package(package_name: str) -> str: ...

@prompt_chain(
    "Search the web for information about {topic} and summarize what you find.",
    functions=[web_search],
)
def search_web_and_summarize(topic: str) -> str: ...

@prompt_chain(
    "Fetch the content from {url} and tell me what kind of page it is.",
    functions=[fetch_url_content],
)
def fetch_and_analyze_url(url: str) -> str: ...

@prompt_chain(
    "Find Nix functions related to {keyword} and list a few examples.",
    functions=[search_nix_functions],
)
def find_nix_functions(keyword: str) -> str: ...


class TestModelIntegration:
    """Tests where the model actually calls the function tools."""
    
    def test_model_calls_nixpkgs_search(self, model_config, request):
        """Test that the model can call search_nixpkgs_for_package."""
        result = print_model_response(
            search_and_describe_package("git"), 
            request
        )
        
        # The model should have called the function and incorporated results
        assert isinstance(result, str)
        assert len(result) > 0
        # Should mention something about git or version control
        assert any(word in result.lower() for word in ["git", "version", "control", "repository"])
    
    def test_model_calls_web_search(self, model_config):
        """Test that the model can call web_search."""
        result = search_web_and_summarize("nixpkgs packaging tutorial")
        
        # The model should have called the function and summarized results
        assert isinstance(result, str)
        assert len(result) > 0
        # Should mention something about nixpkgs or packaging
        assert any(word in result.lower() for word in ["nix", "package", "packaging", "tutorial"])
    
    def test_model_calls_fetch_url(self, model_config):
        """Test that the model can call fetch_url_content."""
        # Use a reliable URL that should work
        result = fetch_and_analyze_url("https://httpbin.org/json")
        
        # The model should have called the function and analyzed the content
        assert isinstance(result, str)
        assert len(result) > 0
        # Should recognize it's a JSON endpoint or API
        assert any(word in result.lower() for word in ["json", "api", "data", "endpoint"])
    
    @pytest.mark.skipif(
        not pytest.importorskip("os").environ.get("NOOGLE_FUNCTION_NAMES"),
        reason="NOOGLE_FUNCTION_NAMES not set - run from nix develop shell"
    )
    def test_model_calls_nix_functions_search(self, model_config):
        """Test that the model can call search_nix_functions."""
        result = find_nix_functions("map")
        
        # The model should have called the function and listed examples
        assert isinstance(result, str)
        assert len(result) > 0
        # Should mention map-related functions or concepts
        assert any(word in result.lower() for word in ["map", "function", "list", "transform"])


# Multi-tool prompt chains
@prompt_chain(
    "Help me find information about packaging {software} for Nix. "
    "First check if it exists in nixpkgs, then search the web for packaging guides.",
    functions=[search_nixpkgs_for_package, web_search],
)
def research_packaging(software: str) -> str: ...

@prompt_chain(
    "I want to package a project from {url}. Fetch the project page and search "
    "for similar packages in nixpkgs to understand how it might be packaged.",
    functions=[fetch_url_content, search_nixpkgs_for_package],
)
def analyze_project_for_packaging(url: str) -> str: ...


class TestMultiToolIntegration:
    """Tests where the model might use multiple tools together."""
    
    def test_model_uses_multiple_search_tools(self, model_config):
        """Test that the model can use nixpkgs search and web search together."""
        result = research_packaging("cowsay")
        
        # Should be a comprehensive response using both tools
        assert isinstance(result, str)
        assert len(result) > 100  # Should be substantial since it uses multiple tools
        assert any(word in result.lower() for word in ["cowsay", "package", "nix"])
    
    def test_model_analyzes_project_with_multiple_tools(self, model_config):
        """Test that the model can fetch URL content and search nixpkgs."""
        # Use a simple, reliable project URL
        result = analyze_project_for_packaging("https://github.com/octocat/Hello-World")
        
        # Should analyze the project and suggest packaging approaches
        assert isinstance(result, str)
        assert len(result) > 50
        # Should mention something about the project or packaging
        assert any(word in result.lower() for word in ["project", "package", "github", "repository"])


# Error handling prompt chains
@prompt_chain(
    "Search for a nonexistent package called {package_name} and tell me what happened.",
    functions=[search_nixpkgs_for_package],
)
def search_nonexistent_package(package_name: str) -> str: ...

@prompt_chain(
    "Try to fetch content from {url} and tell me what you find.",
    functions=[fetch_url_content],
)
def fetch_problematic_url(url: str) -> str: ...


class TestErrorHandling:
    """Test how the model handles tool errors."""
    
    def test_model_handles_no_search_results(self, model_config):
        """Test how the model handles when no packages are found."""
        result = search_nonexistent_package("verylongnonexistentpackagename123")
        
        # Model should gracefully handle the "no results found" response
        assert isinstance(result, str)
        assert len(result) > 0
        assert any(phrase in result.lower() for phrase in ["not found", "no results", "doesn't exist", "unavailable"])
    
    def test_model_handles_fetch_error(self, model_config):
        """Test how the model handles URL fetch errors."""
        result = fetch_problematic_url("https://this-domain-definitely-does-not-exist-12345.com")
        
        # Model should gracefully handle the error response
        assert isinstance(result, str)
        assert len(result) > 0
        assert any(phrase in result.lower() for phrase in ["error", "failed", "unable", "problem", "not accessible"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])