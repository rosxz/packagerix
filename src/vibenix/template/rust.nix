{ lib
, rustPlatform
, fetchFromGitHub
}:

rustPlatform.buildRustPackage rec {
  pname = "{{ pname }}";
  version = "{{ version }}";

  src = {{ src_fetcher }};

  cargoHash = lib.fakeHash;
}