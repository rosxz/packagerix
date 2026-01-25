{ lib
, stdenv
, fetchFromGitHub
, glfw
, libGL
, linux
, makeWrapper
}:

stdenv.mkDerivation rec {
  pname = "YeetMouse";
  version = "unstable-${src.rev}";

  src = fetchFromGitHub {
    owner = "AndyFilter";
    repo = "YeetMouse";
    rev = "b19b6a26106a8335e28436671e652dbf10c180ff";
    hash = "sha256-Q3t9Fa2YAp/yZ88yTg2jzeUel7NeYwmDulOTCqIvnlk=";
  };

  nativeBuildInputs = [ 
    stdenv.cc.cc.lib
    makeWrapper 
    linux.dev  # Explicitly add kernel headers for compilation
  ];

  buildInputs = [ 
    glfw 
    libGL 
  ];

  buildPhase = ''
    cd gui
    make
  '';

  installPhase = ''
    mkdir -p $out/bin
    cp YeetMouseGui $out/bin/YeetMouse
    wrapProgram $out/bin/YeetMouse
  '';
}