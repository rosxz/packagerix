{ lib
, stdenv
, fetchFromGitHub
}:

stdenv.mkDerivation rec {
  pname = "{{ pname }}";
  version = "{{ version }}";

  src = {{ src_fetcher }};
}
