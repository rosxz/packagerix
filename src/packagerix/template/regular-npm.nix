{ lib
, stdenv
, fetchFromGitHub
, buildNpmPackage
}:

buildNpmPackage rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = "v${version}";
    hash = lib.fakeHash;
  };

  npmDepsHash = lib.fakeHash;

  # Common attributes that might be needed:
  # npmFlags = [ "--legacy-peer-deps" ];
  # npmBuildScript = "build";
  # makeCacheWritable = true;
  # dontNpmBuild = true;
}