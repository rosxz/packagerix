{ lib
, python3Packages
, fetchFromGitHub
, cmake
, git
, withMarine ? false
}:

python3Packages.buildPythonApplication rec {
  pname = "pyopenjtalk";
  version = "0.4.1";

  src = fetchFromGitHub {
    owner = "r9y9";
    repo = "pyopenjtalk";
    rev = "v${version}";
    hash = "sha256-f0JNiMCeKpTY+jH3/9LuCkX2DRb9U8sN0SezT6OTm/E=";
    fetchSubmodules = true;
  };

  format = "setuptools";

  nativeBuildInputs = with python3Packages; [
    git
    setuptools
    wheel
    cython
    cmake
  ];

  propagatedBuildInputs = with python3Packages; [
    numpy
    scipy
  ] ++ lib.optionals withMarine [
    # Marine-specific dependencies not yet identified; 
    # placeholder for potential future marine-related packages
  ];

  # Disable CMake build and use setuptools instead
  dontUseCmakeConfigure = true;

  # Create version.py to resolve import error
  postPatch = ''
    echo "__version__ = '${version}'" > pyopenjtalk/version.py
  '';

  pythonImportsCheck = [
    "pyopenjtalk"
  ];
}