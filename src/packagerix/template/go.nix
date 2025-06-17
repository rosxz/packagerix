{ lib
, buildGoModule
, fetchFromGitHub
}:

buildGoModule rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = ...;
    hash = lib.fakeHash;
  };

  vendorHash = lib.fakeHash;  # Use null if no vendor dependencies

  # Build specific package if not building all:
  # subPackages = [ "cmd/your-app" ];
}