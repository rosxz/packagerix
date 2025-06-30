{ lib
, stdenv
, fetchFromGitHub
, nodejs
, pnpm  # You can use specific versions like pnpm_8, pnpm_9, or pnpm_10 instead
, npmHooks
}:
stdenv.mkDerivation rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = ...;
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

    pnpm run build -reporter=append-only
    find dist -type f \( -name '*.cjs' -or -name '*.cts' -or -name '*.ts' \) -delete

    runHook postBuild
  '';
}
