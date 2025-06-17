{ lib
, rustPlatform
, fetchFromGitHub
}:

rustPlatform.buildRustPackage rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = ...;
    hash = lib.fakeHash;
  };

  cargoHash = lib.fakeHash;

  # to make sure we build something sensible
  # we should check for some sort of result
  doInstallCheck = true;
  installCheckPhase = ''
     $out/bin/${pname} --version | grep ${version}
  '';
}