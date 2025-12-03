{ lib
, stdenv
, fetchFromGitHub
}:

stdenv.mkDerivation (finalAttrs: rec {
  pname = "{{ pname }}";
  version = "{{ version }}";

  src = {{ src_fetcher | indent(2) }};
})
