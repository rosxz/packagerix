{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    ciStdenv = pkgs.stdenv // {
      mkDerivation = args: pkgs.stdenv.mkDerivation (args // {
        preBuild = ''
          ${args.preBuild or ""}
          # CI/Non-interactive environment
          export CI=true
          export DEBIAN_FRONTEND=noninteractive
          export NONINTERACTIVE=1
          
          # Terminal and color control
          export TERM=dumb
          export NO_COLOR=1
          export FORCE_COLOR=0
          export CLICOLOR=0
          export CLICOLOR_FORCE=0
          
          # Disable progress bars and spinners
          export PROGRESS_NO_TRUNC=1
        '';
      });
    };
  in
   {

    packages.x86_64-linux.default = pkgs.lib.callPackageWith (
      pkgs // { stdenv = ciStdenv; }) ./package.nix {};
    packages.x86_64-linux.nixpkgs-src = nixpkgs.outPath;

    # VM configuration for nixos-shell testing
    nixosConfigurations.vm = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [
        ({ modulesPath, ... }: {
          imports = [ 
            "${modulesPath}/profiles/minimal.nix"
            #"${modulesPath}/profiles/headless.nix"
          ];

          # Use same nixpkgs in VM's NIX_PATH
          nix.nixPath = [ "nixpkgs=${nixpkgs.outPath}" ];
          nix.registry.nixpkgs.flake = nixpkgs;

          # Minimal VM configuration
          documentation = {
            enable = false;
            doc.enable = false;
            man.enable = false;
            info.enable = false;
            nixos.enable = false;
          };
          
          # Include the package being tested
          environment.systemPackages = 
            let 
              pkg = self.packages.${system}.default;
              # Try to create Python with the package; falls back to just pkg if it's not a Python package
              pythonWithPkg = builtins.tryEval (pkgs.python3.withPackages (ps: [ pkg ]));
            in 
              [ pkg ] ++ (if pythonWithPkg.success then [ pythonWithPkg.value ] else [ pkgs.python3 ]);

          # Basic VM settings
          virtualisation = {
            graphics = false;
            #memorySize = 1024;
          };

          users.users.test = {
            isNormalUser = true;
            extraGroups = [ "wheel" ];
            password = "test";
          };
          users.users.root.hashedPassword = "*"; # Disable root user
          users.mutableUsers = false;

          # CI/Non-interactive environment variables
          environment.sessionVariables = {
            CI = "true";
            DEBIAN_FRONTEND = "noninteractive";
            NONINTERACTIVE = "1";
            TERM = "dumb";
            NO_COLOR = "1";
            FORCE_COLOR = "0";
            CLICOLOR = "0";
            CLICOLOR_FORCE = "0";
            PROGRESS_NO_TRUNC = "1";
          };

          # Prevent mounting home directory for better isolation
          nixos-shell.mounts.mountHome = false;

          nix = {
            settings.experimental-features = [ "nix-command" "flakes" ];
            settings.substituters = [ "https://cache.nixos.org" ];
            settings.trusted-public-keys = [ "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY=" ];
          };

          # Enable sudo without password for testing
          security.sudo.wheelNeedsPassword = false;

          # SSH and Port Forwarding to allow running commands on the VM
          services.openssh.enable = true;
          virtualisation.forwardPorts = [
            { from = "host"; host.port = 2222; guest.port = 22; }
          ];
        })
      ];
    };

  };
}
