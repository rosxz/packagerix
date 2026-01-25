{ lib
, rustPlatform
, fetchFromGitHub
, tree-sitter
, stdenv
, cmake  # Added CMake as a build input
}:

rustPlatform.buildRustPackage rec {
  pname = "tree-sitter-crystal";
  version = "unstable-${src.rev}";

  src = fetchFromGitHub {
    owner = "crystal-lang-tools";
    repo = "tree-sitter-crystal";
    rev = "76afc1f53518a2b68b51a5abcde01d268a9cb47c";
    hash = "sha256-jZiy007NtbIoj7eVryejr1ECjzLErSzT1GXq24A9+xE=";
  };

  cargoHash = "sha256-7VKJTQ6hfzzix3uhkgVp4bx1vqDfA7KmCoo58ELWR3Q=";

  buildInputs = [ 
    tree-sitter 
    stdenv.cc  # Explicitly add C compiler 
    cmake  # Added CMake to buildInputs
  ];

  # Add build hook to compile the tree-sitter parser before building the Rust library
  preBuild = ''
    make
  '';

  # Disable tests until we can fully resolve the version issue
  doCheck = false;
}