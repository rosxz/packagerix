{ lib
, buildGoModule
, fetchFromGitHub
, systemd ? null
, zerotier ? null
}:

buildGoModule rec {
  pname = "zerotier-systemd-manager";
  version = "0.4.0";

  src = fetchFromGitHub {
    owner = "zerotier";
    repo = "zerotier-systemd-manager";
    rev = "v${version}";
    hash = "sha256-vq6AqrA9ryzLcLEsPD2KbBZhF5YjF48ErIWb8e3b9JI=";
  };

  vendorHash = "sha256-40e/FFzHbWo0+bZoHQWzM7D60VUEr+ipxc5Tl0X9E2A=";

  # Explicitly include ZeroTier Go module dependency
  vendorWants = [
    "github.com/zerotier/go-zerotier-one@v0.1.1"
  ];

  propagatedBuildInputs = [
    systemd
  ] ++ lib.optionals (zerotier != null) [ zerotier ];

  doInstallCheck = true;
  installCheckPhase = ''
    $out/bin/zerotier-systemd-manager --help
  '';
}