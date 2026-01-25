{ lib
, python3Packages
, fetchFromGitHub
, libsodium  # Added LibSodium dependency
}:

python3Packages.buildPythonApplication rec {
  pname = "globaleaks-whistleblowing-software";
  version = "5.0.72";

  src = fetchFromGitHub {
    owner = "globaleaks";
    repo = "globaleaks-whistleblowing-software";
    rev = "v${version}";
    hash = "sha256-iIENcF0qZ3wY6ap1wJLO3dcgtDvMLjnjKQKeCkh8QUc=";
  };

  # Use pyproject for modern Python project
  pyproject = true;

  # Build system dependencies
  build-system = with python3Packages; [
    setuptools
  ];

  # Runtime dependencies from project's requirements
  dependencies = with python3Packages; [
    sqlalchemy_1_4
    twisted
    txtorcon
    pynacl
    pyotp            # Added
    cryptography     # Added
    python-gnupg     # Added
  ];

  # Add LibSodium as a build input
  buildInputs = [
    libsodium
  ];

  # Use the backend directory for build and installation
  sourceRoot = "source/backend";

  pythonImportsCheck = [
    "globaleaks"
  ];
}