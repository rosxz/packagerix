{ lib
, stdenv
, fetchFromGitHub
, buildNpmPackage
, nodejs
}:

buildNpmPackage rec {
  pname = "wud";
  version = "8.1.1";

  src = fetchFromGitHub {
    owner = "getwud";
    repo = "wud";
    rev = "${version}";
    hash = "sha256-h9p0l6MuCErYoeDEc1z1oIP/SV4v/V2H4a6Jk5MQeis=";
  };

  npmDepsHash = "sha256-tCsim+MF3AH0+IX0PiZEZUiiOTE9b0FxeFiatCiHKFA=";

  postPatch = ''
    cd app
    cp package-lock.json ../
    cp package.json ../
    cd ..
  '';

  dontNpmBuild = true;

  installCheckPhase = ''
    nodejs $out/bin/index.js --help
  '';
}