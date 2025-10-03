{ lib
, rustPlatform
, fetchFromGitHub
}:

rustPlatform.buildRustPackage rec {
  pname = "{{ pname }}";
  version = "{{ version }}";

  src = {{ src_fetcher | indent(2) }};

  cargoHash = lib.fakeHash;
}
