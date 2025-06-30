{ lib
, fetchFromGitHub
, buildDartApplication
}:

buildDartApplication rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = ...;
    hash = lib.fakeHash;
  };

  # Required: pubspec.lock must be converted to JSON
  # 1. Build once with autoPubspecLock = ./path/to/pubspec.lock;
  # 2. Or generate manually: yq . pubspec.lock > pubspec.lock.json
  pubspecLock = lib.importJSON ./pubspec.lock.json;

  # For packages from git repositories, specify commit hashes:
  # gitHashes = {
  #   package_name = "sha256-...";
  # };

  # Additional build dependencies:
  # nativeBuildInputs = [ buf protoc-gen-dart ];

  # Pre-build setup (e.g., for protobuf generation):
  # preConfigure = ''
  #   HOME="$TMPDIR" buf generate
  # '';

  # Dart compilation flags:
  # dartCompileFlags = [ "--define=version=${version}" ];

  # Output type (default is "exe", other options: "aot-snapshot", "jit-snapshot", "kernel", "js"):
  # dartOutputType = "exe";

  # Entry points (defaults to reading from pubspec.yaml):
  # dartEntryPoints = {
  #   "bin/my-app" = "bin/main.dart";
  # };

  # Runtime dependencies (added to PATH):
  # runtimeDependencies = [ somePackage ];

  # Post-install steps:
  # postInstall = ''
  #   # Create symlinks for alternative binary names
  #   ln -s $out/bin/${pname} $out/bin/alternate-name
  # '';
}