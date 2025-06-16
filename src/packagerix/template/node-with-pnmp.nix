{ lib
, stden
, fetchFromGitHub
, nodejs
, pnpm
, npmHooks
}:
let
  # pick different pnpm version e.g. pnpm_9 or pnpm_10
  pnpm = pnpm;
in
stdenv.mkDerivation rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = "v${version}";
    hash = lib.fakeHash;
  };

  pnpmDeps = pnpm.fetchDeps {
    inherit pname version src;
    hash = lib.fakeHash;
  };

  nativeBuildInputs = [
    nodejs
    pnpm.configHook
    npmHooks.npmInstallHook
  ];

  buildPhase = ''
    runHook preBuild

    pnpm run build
    find dist -type f \( -name '*.cjs' -or -name '*.cts' -or -name '*.ts' \) -delete

    runHook postBuild
  '';
}
