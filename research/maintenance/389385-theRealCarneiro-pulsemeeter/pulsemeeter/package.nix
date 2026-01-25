{ lib
, python3Packages
, fetchFromGitHub
, gobject-introspection
, gtk3
, libpulseaudio
, libappindicator
}:

python3Packages.buildPythonApplication rec {
  pname = "pulsemeeter";
  version = "1.2.14";

  src = fetchFromGitHub {
    owner = "theRealCarneiro";
    repo = "pulsemeeter";
    rev = "v${version}";
    hash = "sha256-QTXVE5WvunsjLS8I1rgX34BW1mT1UY+cRxURwXiQp5A=";
  };

  pyproject = true;

  nativeBuildInputs = [
    gobject-introspection
    python3Packages.setuptools
  ];

  buildInputs = [
    gtk3
    libpulseaudio
    libappindicator
  ];

  propagatedBuildInputs = with python3Packages; [
    pygobject3
    pycairo
    python-daemon
    dbus-python
    pulsectl
  ];

  pythonImportsCheck = [
    "pulsemeeter"
  ];

  # Ensures all packages, including subpackages, are discovered
  pythonPackagePaths = [ "." ];
}