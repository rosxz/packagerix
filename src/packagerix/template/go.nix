{ lib
, buildGoModule
, fetchFromGitHub
, installShellFiles  # Add if the application has shell completions
}:

buildGoModule rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = "v${version}";
    hash = lib.fakeHash;
  };

  vendorHash = lib.fakeHash;  # Use null if no vendor dependencies

  # nativeBuildInputs = [ installShellFiles ];  # Uncomment if needed

  # Build specific package if not building all:
  # subPackages = [ "cmd/your-app" ];

  # Common ldflags for version info and smaller binaries:
  # ldflags = [
  #   "-s"
  #   "-w" 
  #   "-X main.version=${version}"
  # ];

  # Disable CGO for static binaries:
  # env.CGO_ENABLED = 0;

  # Custom build tags:
  # tags = [ "netgo" ];

  # Install shell completions (if supported):
  # postInstall = lib.optionalString (stdenv.buildPlatform.canExecute stdenv.hostPlatform) ''
  #   installShellCompletion --cmd ${pname} \
  #     --bash <($out/bin/${pname} completion bash) \
  #     --fish <($out/bin/${pname} completion fish) \
  #     --zsh <($out/bin/${pname} completion zsh)
  # '';

  # Version checking:
  # doInstallCheck = true;
  # installCheckPhase = ''
  #   $out/bin/${pname} version | grep ${version}
  # '';
}