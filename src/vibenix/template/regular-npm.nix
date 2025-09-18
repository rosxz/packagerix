{ lib
, stdenv
, fetchFromGitHub
, buildNpmPackage
}:

buildNpmPackage rec {
  pname = "{{ pname }}";
  version = "{{ version }}";

  src = {{ src_fetcher | indent(2) }};

  npmDepsHash = lib.fakeHash;

  # Common attributes that might be needed:
  # npmFlags = [ "--legacy-peer-deps" ];
  # npmBuildScript = "build";
  # makeCacheWritable = true;
  # dontNpmBuild = true;
}
