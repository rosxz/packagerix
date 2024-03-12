{
  description = "Application packaged using poetry2nix";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:Arkptz/poetry2nix/c699e8bf5b5401ed9f32c857ab945168d3ee129b";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    magentic = {
     url = github:jackmpcollins/magentic;
     flake = false;
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix, magentic }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # see https://github.com/nix-community/poetry2nix/tree/master#api for more functions and examples.
        pkgs = nixpkgs.legacyPackages.${system};
        p2n = poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
        pyPkgs = pkgs.python311Packages;
        inherit (p2n) mkPoetryApplication mkPoetryPackages;
      in
      {
        packages = {
          magentic = mkPoetryApplication rec {
            projectDir = magentic;
            overrides = p2n.defaultPoetryOverrides.extend (self: super: {
              pprintpp = null;
              tiktoken = pyPkgs.tiktoken;
              tokenizers = pyPkgs.tokenizers;
              litellm = pyPkgs.litellm.override {
                openai = pyPkgs.openai.override {
                  pydantic = pyPkgs.pydantic;
                };
              };
              openai = pyPkgs.openai;
              typing_extensions = pyPkgs.typing_extensions;
              pydantic = pyPkgs.pydantic;
              pydantic-settings = pyPkgs.pydantic-settings;
            });
          };
          default = self.packages.${system}.magentic;
        };

        devShells.default = pkgs.mkShell {
          MAGENTIC_BACKEND = "litellm";
          MAGENTIC_LITELLM_MODEL = "ollama/phi";
          packages = [
            pkgs.poetry
            pyPkgs.packaging # TODO: add this to litellm dependencies instead
              (pkgs.python311.withPackages (ps: with ps; [ self.packages.${system}.magentic pyPkgs.beautifulsoup4 ]))
          ];
        };
      });
}
