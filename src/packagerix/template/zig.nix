{ lib
, stdenv
, fetchFromGitHub
, zig_0_13  # Choose appropriate Zig version (zig_0_11, zig_0_12, zig_0_13, zig_0_14, etc.)
}:

let
  zig = zig_0_13;  # Or use a specific version
in
stdenv.mkDerivation rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = ...;
    hash = lib.fakeHash;
  };

  nativeBuildInputs = [
    zig.hook
  ];
}