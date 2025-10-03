{ lib
, stdenv
, fetchFromGitHub
, zig_0_13  # Choose appropriate Zig version (zig_0_11, zig_0_12, zig_0_13, zig_0_14, etc.)
}:

let
  zig = zig_0_13;  # Or use a specific version
in
stdenv.mkDerivation rec {
  pname = "{{ pname }}";
  version = "{{ version }}";

  src = {{ src_fetcher | indent(2) }};

  nativeBuildInputs = [
    zig.hook
  ];
}
