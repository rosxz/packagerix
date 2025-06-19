{
  description = "Application packaged using uv2nix";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    magentic = {
     url = "github:jackmpcollins/magentic/v0.39.3";
     flake = false;
    };
  };

  outputs = { self, nixpkgs, flake-utils, pyproject-nix, uv2nix, magentic }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        # Load the workspace
        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

        # Create overlay
        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        # Python package set
        pythonSet = (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope overlay;
      in
      {
        packages = {
          # Create a virtual environment with all dependencies
          default = pythonSet.mkVirtualEnv "packagerix-env" workspace.deps.default;

          # The packagerix application itself
          packagerix = pythonSet.packagerix;
        };

        devShells = {
          default = pkgs.mkShell {
            MAGENTIC_BACKEND = "litellm";
            OLLAMA_HOST= "https://hydralisk.van-duck.ts.net:11435";
#            MAGENTIC_LITELLM_MAX_TOKENS = "1024";
#             ANTHROPIC_LOG="debug";

            # Use only dependencies environment, not the built package
            packages = [
              python
              (pythonSet.mkVirtualEnv "packagerix-dev-deps" workspace.deps.default)
              pkgs.nurl
              pkgs.jq
            ];

            # Point to source files for development
            PYTHONPATH = "src";
          };

          # Impure shell for generating uv.lock
          impure = pkgs.mkShell {
            packages = [
              python
              pkgs.uv
            ];
            shellHook = ''
              unset PYTHONPATH
            '';
            UV_PYTHON_DOWNLOADS = "never";
            UV_PYTHON = "${python}/bin/python";
            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
              pkgs.stdenv.cc.cc.lib
            ];
          };
        };
      });
}
