{ lib
, fetchFromGitHub
, flutter329  # Or flutter327, flutter338, etc. - check available versions
# Platform-specific dependencies for Linux desktop:
, libdrm      # For WebRTC support
, libgbm      # For WebRTC support
, pulseaudio  # For audio support
, mpv-unwrapped  # For media playback (if needed)
, libass      # For subtitle support (if needed)
# Build tools:
, imagemagick # For icon generation
, makeDesktopItem
}:

let
  # Choose the appropriate Flutter version
  flutter = flutter329;
in
flutter.buildFlutterApplication rec {
  pname = ...;
  version = ...;

  src = fetchFromGitHub {
    owner = ...;
    repo = ...;
    rev = ...;
    hash = lib.fakeHash;
  };

  # Required: pubspec.lock must be converted to JSON
  # Generate with: yq . pubspec.lock > pubspec.lock.json
  pubspecLock = lib.importJSON ./pubspec.lock.json;

  # For packages from git repositories, specify commit hashes:
  # gitHashes = {
  #   package_name = "sha256-...";
  # };

  # Target platform (default: "linux", other options: "web"):
  targetFlutterPlatform = "linux";

  # Native build dependencies:
  nativeBuildInputs = [ imagemagick ];

  # Runtime dependencies:
  runtimeDependencies = [ pulseaudio ];

  # Build inputs (compile-time dependencies):
  # buildInputs = [ mpv-unwrapped libass ];

  # For apps using WebRTC or similar native libraries:
  # env.NIX_LDFLAGS = "-rpath-link ${lib.makeLibraryPath [ libgbm libdrm ]}";

  # Flutter build flags:
  # flutterBuildFlags = [ "--release" "--no-sound-null-safety" ];

  # Desktop file for Linux apps:
  desktopItem = makeDesktopItem {
    name = pname;
    exec = pname;
    icon = pname;
    desktopName = "App Name";
    genericName = "App Description";
    categories = [ "Utility" ];  # Adjust as needed
  };

  # Post-install for Linux desktop:
  postInstall = ''
    # Install icons
    FAV=$out/app/${pname}-linux/data/flutter_assets/assets/icon.png
    ICO=$out/share/icons

    install -D $FAV $ICO/${pname}.png
    
    # Generate multiple icon sizes
    for size in 16 24 32 48 64 128 256 512; do
      D=$ICO/hicolor/''${size}x''${size}/apps
      mkdir -p $D
      convert $FAV -resize ''${size}x''${size} $D/${pname}.png
    done

    # Install desktop file
    mkdir -p $out/share/applications
    cp $desktopItem/share/applications/*.desktop $out/share/applications

    # Patch native libraries if needed:
    # patchelf --add-rpath ${lib.makeLibraryPath [ libgbm libdrm ]} \
    #   $out/app/${pname}-linux/lib/libwebrtc.so
  '';

}