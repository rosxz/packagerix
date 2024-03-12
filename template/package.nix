{ lib
, stdenv
, fetchurl
, installShellFiles
, libbsd
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

  meta = with lib; {
    homepage = ...;
    description = ...;
    longDescription = ...;
    license = ...;
    maintainers = with maintainers; [];
    platforms = platforms.unix;
  };
}
