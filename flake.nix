{
  description = "Application packaged using poetry2nix";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:mschwaig/poetry2nix/build-magentic";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    magentic = {
     url = "github:jackmpcollins/magentic/v0.28.1";
     flake = false;
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix, magentic }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # see https://github.com/nix-community/poetry2nix/tree/master#api for more functions and examples.
        pkgs = nixpkgs.legacyPackages.${system};
        p2n = poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
        pyPkgs = pkgs.python312Packages;
        inherit (p2n) mkPoetryApplication mkPoetryPackages;
      in
      {
        packages = {
          magentic = mkPoetryApplication rec {
            projectDir = magentic;
            python = pkgs.python312;
            overrides = p2n.defaultPoetryOverrides.extend (self: super: {
              jiter = pyPkgs.jiter; #super.jiter.override { preferWheel = true; };
              logfire-api = super.logfire-api.override { preferWheel = true; };
              logfire = super.logfire.override { preferWheel = true; };
              pprintpp = null;
              tiktoken = pyPkgs.tiktoken;
              tokenizers = pyPkgs.tokenizers;
              idna = pyPkgs.idna;
              anthropic = pyPkgs.anthropic;
              litellm = pyPkgs.litellm;
              openai = pyPkgs.openai;
              pydantic = pyPkgs.pydantic;
              pydantic-settings = pyPkgs.pydantic-settings;
            });
          };
          default = self.packages.${system}.magentic;
        };

        devShells.default = pkgs.mkShell {
#          MAGENTIC_BACKEND = "litellm";
          MAGENTIC_BACKEND = "openai";
#          MAGENTIC_BACKEND = "anthropic";
          MAGENTIC_ANTHROPIC_MODEL = "claude-3-5-sonnet-20240620";
#          MAGENTIC_OPENAI_MODEL = "gpt-3.5-turbo";
          MAGENTIC_OPENAI_MODEL = "gpt-4o";
          MAGENTIC_LITELLM_MAX_TOKENS = "1024";
#          MAGENTIC_LITELLM_MODEL =  "anthropic/claude-3-5-sonnet-20240620";
#          MAGENTIC_LITELLM_MODEL =  "ollama/phi3";
#          MAGENTIC_LITELLM_MODEL =  "ollama/llama3.1:70b";
#          MAGENTIC_LITELLM_MODEL =  "anthropic/claude-3-haiku-20240307";
           ANTHROPIC_LOG="debug";
          packages = [
            (pkgs.python312.withPackages (ps: with ps; [ self.packages.${system}.magentic pyPkgs.beautifulsoup4 pyPkgs.diskcache pyPkgs.gitpython ]))
          ];
        };
      });
}
