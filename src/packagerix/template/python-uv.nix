{ lib
, python3Packages
, fetchFromGitHub
}:

python3Packages.buildPythonApplication rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = "v${version}";
    hash = lib.fakeHash;
  };

  pyproject = true;

  # Use uv-build as the build backend
  build-system = with python3Packages; [
    uv-build
  ];

  # Runtime dependencies from pyproject.toml
  dependencies = with python3Packages; [
    # List runtime dependencies here
  ];

  # If the project has a uv.lock file, you may need to handle it:
  # preBuild = ''
  #   # UV typically expects to manage dependencies itself
  #   # In Nix, we need to ensure it uses our pre-fetched dependencies
  #   export UV_NO_SYNC=1
  # '';

  # Test dependencies
  nativeCheckInputs = with python3Packages; [
    pytestCheckHook
    # Add other test dependencies
  ];

  # UV projects might need specific environment variables
  # env = {
  #   UV_PYTHON = "${python3Packages.python.interpreter}";
  # };

  pythonImportsCheck = [ pname ];

  # If tests require network access or UV features:
  # doCheck = false;
  # Or disable specific tests:
  # pytestFlagsArray = [
  #   "-k 'not test_requiring_uv_sync'"
  # ];
}