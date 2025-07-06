{ lib
, stdenv
, python3
, nix
, jq
, nixpkgs
, fetchgit
}:

let
  python = python3.withPackages (ps: with ps; [
    sentence-transformers
    scikit-learn
    numpy
  ]);
  
  # Pre-fetch the model to avoid network access during build
  modelData = fetchgit {
    url = "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2";
    rev = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf";
    hash = "sha256-9pSkyGluKYlFOBCdXykx1KbjLYQ/MeEhV4x85LG6ECw=";
    fetchLFS = true;
  };
in
stdenv.mkDerivation rec {
  pname = "nixpkgs-package-embeddings";
  version = "unstable-2024-01-05";

  nativeBuildInputs = [ nix jq python ];

  # We don't have a source, we generate the data
  dontUnpack = true;

  buildPhase = ''
    # Set up temporary directories for nix state to avoid permission issues
    export NIX_STATE_DIR=$TMPDIR/nix/var/nix
    export NIX_DATA_DIR=$TMPDIR/nix/share
    export NIX_LOG_DIR=$TMPDIR/nix/var/log/nix
    export NIX_CONF_DIR=$TMPDIR/nix/etc/nix
    mkdir -p $NIX_STATE_DIR $NIX_DATA_DIR $NIX_LOG_DIR $NIX_CONF_DIR
    
    # Use nix-env which works better in sandbox
    echo "Fetching package list from nixpkgs..."
    
    # Get all packages using nix-env with attribute paths
    nix-env -f ${nixpkgs} -qaP --json --meta > packages_raw.json
    
    # Transform to match the expected format
    echo "Processing package data..."
    jq 'to_entries | map({
      key: .key,
      value: {
        version: .value.version,
        description: (.value.meta.description // "")
      }
    })' packages_raw.json > processed_packages.json

    # Generate embeddings using Python with pre-fetched model
    echo "Generating embeddings..."
    echo "Model files:"
    ls -la ${modelData}/
    export SENTENCE_TRANSFORMER_MODEL=${modelData}
    export TRANSFORMERS_OFFLINE=1
    export HF_DATASETS_OFFLINE=1
    python ${./generate-embeddings.py} processed_packages.json embeddings.pkl
  '';

  installPhase = ''
    mkdir -p $out
    cp embeddings.pkl $out/
    
    # Also save metadata
    echo "{\"version\": \"${version}\", \"package_count\": $(jq 'length' processed_packages.json)}" > $out/metadata.json
  '';
}
