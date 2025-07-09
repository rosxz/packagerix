"""Tests for function_calls module using LiteLLM models."""

import pytest
import os
import json
from unittest.mock import patch, MagicMock
from vibenix.tools import search_nixpkgs_for_package_literal, search_nixpkgs_for_package_semantic, search_nix_functions
from vibenix.tools.file_tools import create_source_function_calls


class TestSearchNixpkgsForPackage:
    """Tests for search_nixpkgs_for_package functions."""
    
    def test_search_returns_json(self):
        """Test that search returns valid JSON output."""
        # Mock the subprocess.run to avoid actual nix calls
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({
                "cowsay": {
                    "description": "Program which generates ASCII pictures of a cow with a message",
                    "pname": "cowsay",
                    "version": "3.8.4"
                }
            })
            mock_run.return_value = mock_result
            
            result = search_nixpkgs_for_package_literal("cowsay")
            
            # Verify it returns JSON
            parsed = json.loads(result)
            assert "cowsay" in parsed
            assert parsed["cowsay"]["pname"] == "cowsay"
    
    def test_search_no_results(self):
        """Test search with no results."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            
            result = search_nixpkgs_for_package_literal("nonexistentpackage123")
            assert "no results found" in result
    
    def test_search_command_format(self):
        """Test that the search command uses the correct format with jq."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "{}"
            mock_run.return_value = mock_result
            
            search_nixpkgs_for_package_literal("test")
            
            # Verify the command includes nix search --json and jq pipeline
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "nix search --json nixpkgs test" in args
            assert "jq" in args
            assert "legacyPackages" in args

class TestListDirectoryContents:
    """Tests for list_directory_contents function."""
    functions = create_source_function_calls("/nix")
    
    def test_list_directory_contents_success(self):
        """Test successful listing of directory contents."""
        list_function = self.functions[0]  # TODO this could be improved

        result = list_function(".")
        assert "store" in result
    
    def test_list_directory_contents_invalid_path(self):
        """Test listing contents of an invalid path."""
        list_function = self.functions[0]

        result = list_function("absdjweflTHIS_WILL_NEVER_APPEAR")
        assert "Failed to list contents" in result

    def test_list_directory_contents_outside_store(self):
        """Test listing contents of an invalid path."""
        list_function = self.functions[0]

        result = list_function("../")
        assert "is outside the allowed root directory" in result

class TestSearchNixFunctions:
    """Tests for search_nix_functions function."""
    
    def test_search_nix_functions_no_env_var(self):
        """Test when NOOGLE_FUNCTION_NAMES is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = search_nix_functions("map")
            assert "NOOGLE_FUNCTION_NAMES environment variable not set" in result
    
    def test_search_nix_functions_file_not_found(self):
        """Test when the function names file doesn't exist."""
        with patch.dict(os.environ, {"NOOGLE_FUNCTION_NAMES": "/nonexistent/file"}):
            result = search_nix_functions("map")
            assert "Noogle function names file not found" in result
    
    def test_search_nix_functions_success(self):
        """Test successful function search using real NOOGLE data."""
        # Skip if NOOGLE_FUNCTION_NAMES not set in environment
        if not os.environ.get("NOOGLE_FUNCTION_NAMES"):
            pytest.skip("NOOGLE_FUNCTION_NAMES not set - run from nix develop shell")
        
        # Test with a common Nix function that should exist
        result = search_nix_functions("map")
        # Should return results or no matches, but not an error
        assert "Error searching Nix functions" not in result
        assert "fzf not found" not in result
    
    def test_search_nix_functions_no_results(self):
        """Test when no functions match."""
        # Skip if NOOGLE_FUNCTION_NAMES not set in environment
        if not os.environ.get("NOOGLE_FUNCTION_NAMES"):
            pytest.skip("NOOGLE_FUNCTION_NAMES not set - run from nix develop shell")
        
        # Use a very unlikely search term
        result = search_nix_functions("verylongnonexistentfunctionname123")
        assert "No Nix functions found" in result or result.strip() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
