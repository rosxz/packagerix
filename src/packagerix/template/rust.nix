{ lib
, rustPlatform
, fetchFromGitHub
, installShellFiles  # Add if the application has shell completions
, pkg-config         # Add if needed for native dependencies
# Common native dependencies:
# , openssl
# , zlib
# , sqlite
}:

rustPlatform.buildRustPackage rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = "v${version}";
    hash = lib.fakeHash;
  };

  useFetchCargoVendor = true;
  cargoHash = lib.fakeHash;

  # nativeBuildInputs = [ installShellFiles pkg-config ];
  # buildInputs = [ openssl zlib ];

  # Build specific features:
  # buildFeatures = [ "feature1" "feature2" ];
  # buildNoDefaultFeatures = true;

  # Generate shell completions and man pages (if supported):
  # postInstall = ''
  #   installShellCompletion --cmd ${pname} \
  #     --bash <($out/bin/${pname} completions bash) \
  #     --fish <($out/bin/${pname} completions fish) \
  #     --zsh <($out/bin/${pname} completions zsh)
  #   
  #   $out/bin/${pname} --help-man > ${pname}.1
  #   installManPage ${pname}.1
  # '';

  # Disable flaky tests:
  # doCheck = false;
  # Or exclude specific tests:
  # checkFlags = [
  #   "--skip=test_name"
  #   "--skip=flaky_test"
  # ];

  # Install check:
  # doInstallCheck = true;
  # installCheckPhase = ''
  #   $out/bin/${pname} --version | grep ${version}
  # '';
}