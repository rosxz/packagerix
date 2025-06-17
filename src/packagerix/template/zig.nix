{ lib
, stdenv
, fetchFromGitHub
, zig_0_13  # Choose appropriate Zig version (zig_0_11, zig_0_12, zig_0_13, zig_0_14, etc.)
, callPackage
, installShellFiles  # Add if installing man pages or shell completions
# Common dependencies for Zig projects:
# , pkg-config
# , wayland
# , libGL
# , xorg
}:

let
  zig = zig_0_13;  # Or use a specific version
in
stdenv.mkDerivation (finalAttrs: {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  nativeBuildInputs = [
    zig.hook
    # installShellFiles
    # pkg-config
  ];

  # buildInputs = [
  #   # Add C libraries if needed
  # ];

  # For projects with dependencies in build.zig.zon:
  # deps = callPackage ./deps.nix { };
  # OR for newer format:
  # deps = callPackage ./build.zig.zon.nix { };

  # Then link dependencies:
  # postPatch = ''
  #   ln -s ${finalAttrs.deps} $ZIG_GLOBAL_CACHE_DIR/p
  # '';
  # OR use with --system flag:
  # zigBuildFlags = [ "--system" "${finalAttrs.deps}" ];

  # Common build flags:
  # zigBuildFlags = [
  #   "-Doptimize=ReleaseSafe"  # or ReleaseFast, ReleaseSmall
  #   "-Dcpu=baseline"  # for better compatibility
  #   "-Dstrip=true"  # strip debug info
  #   # Custom feature flags:
  #   "-Denable-feature=true"
  # ];

  # Run tests (enabled by default):
  # doCheck = true;
  # zigCheckFlags = [ ];
  # Or disable tests:
  # dontUseZigCheck = true;

  # Install additional files:
  # postInstall = ''
  #   installManPage man/${finalAttrs.pname}.1
  #   installShellCompletion --cmd ${finalAttrs.pname} \
  #     --bash completions/bash \
  #     --fish completions/fish \
  #     --zsh completions/zsh
  # '';

  meta = {
    description = "";
    homepage = "";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ ];
    mainProgram = finalAttrs.pname;
    inherit (zig.meta) platforms;
  };
})