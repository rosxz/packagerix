{ lib
, stdenv
, fetchFromGitHub
, nodejs
, electron
, pnpm
, npmHooks
}:
stdenv.mkDerivation rec {
  pname = "SPlayer";
  version = "3.0.0-beta.1";

  src = fetchFromGitHub {
    owner = "imsyy";
    repo = "SPlayer";
    rev = "v${version}";
    hash = "sha256-Sw5L474gowpOVkIc3CHWVEzknMgJvBmtNXRCxzwY8BA=";
  };

  pnpmDeps = pnpm.fetchDeps {
    inherit pname version src;
    hash = "sha256-mC1iJtkZpTd2Vte5DLI3ntZ7vSO5Gka2qOk7ihQd3Gs=";
  };

  nativeBuildInputs = [
    nodejs
    pnpm.configHook
    npmHooks.npmInstallHook
  ];

  buildInputs = [
    electron
  ];

  buildPhase = ''
    runHook preBuild

    pnpm run typecheck
    pnpm run build

    find out/renderer -type f \( -name '*.cjs' -or -name '*.cts' -or -name '*.ts' \) -delete

    runHook postBuild
  '';

  installPhase = ''
    mkdir -p $out
    cp -r out/renderer $out/
  '';

  installCheckPhase = ''
    test -d $out/renderer
    test -n "$(find $out/renderer -type f)"
  '';

  doInstallCheck = true;
}