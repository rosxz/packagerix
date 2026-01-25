{ lib
, buildGoModule
, fetchFromGitHub
, bun  # Added Bun as a dependency
}:

buildGoModule rec {
  pname = "jxscout";
  version = "0.9.2";

  src = fetchFromGitHub {
    owner = "francisconeves97";
    repo = "jxscout";
    rev = "v${version}";
    hash = "sha256-6ane5O/lNRXMPgqjneOHBwQcAuiwQwTtqnE1TcSORes=";
  };

  vendorHash = null;  # Set to null as the vendor folder exists

  # Add Bun as a runtime dependency
  nativeBuildInputs = [ bun ];

  # Provide more verbose test output to help diagnose the issue
  GO_TEST_VERBOSE = "1";

  # Build all packages in the project
  subPackages = [ "." ];

  # Optional: Add build flags to help with debugging
  buildFlags = [ "-v" ];

  # Enable tests
  doCheck = true;

  # Optional: Increase test timeout
  checkFlags = [ "-timeout=10m" ];
}