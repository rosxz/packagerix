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

    # VM configuration for nixos-shell testing with SSH
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

          # Create symlink to the package in test user's home
          system.activationScripts.packageSymlink = ''
            mkdir -p /home/test
            ln -sfn ${self.packages.${system}.default} /home/test/package
            chown -h test:users /home/test/package
          '';

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

    # VM configuration for script-based testing (simpler, stateless)
    nixosConfigurations.vm-script = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [
        ({ modulesPath, ... }: {
         # imports = [
         #   "${modulesPath}/profiles/minimal.nix"
         # ];

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
          # Import packages configuration (written by Python in flake directory)
          environment.systemPackages =
            let
              pkg = self.packages.${system}.default;
              # Import the packages file with pkg and pkgs in scope
              result = builtins.scopedImport { inherit pkgs pkg; } ./packages.nix;
            in
              # Validate that the result is a list (safety check against sandbox escapes)
              assert builtins.isList result;
              # Add bash and coreutils for script execution
              result ++ [ pkgs.bash pkgs.coreutils ];

          # Create symlink to the package in test user's home
          system.activationScripts.packageSymlink = ''
            mkdir -p /home/test
            ln -sfn ${self.packages.${system}.default} /home/test/package
            chown -h test:users /home/test/package
          '';

          # Basic VM settings
          virtualisation = {
            graphics = false;
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

          # Mount shared folder for script execution
          nixos-shell.mounts.extraMounts = {
            "/task" = {
              target = "{{ flake_dir }}/vm-task";
              cache = "none";  # see writes immediately
            };
          };

          # Disable network access for security
          virtualisation.qemu.networkingOptions = [];

          # Disable Nix daemon but keep basic utilities
          nix.enable = false;

          # Enable sudo without password for testing
          security.sudo.wheelNeedsPassword = false;

          # Systemd service to run the task script and shutdown
          systemd.services.run-task = {
            wantedBy = [ "multi-user.target" ];
            # Ensure the mount is available before running
            requires = [ "task.mount" ];
            after = [ "multi-user.target" "task.mount" ];
            serviceConfig = {
              Type = "oneshot";
              User = "root"; # Need root to write to /task and poweroff
            };
            script = ''
              set -x
              # Wait for /task to be available
              for i in {1..10}; do
                if [ -d /task ]; then
                  break
                fi
                sleep 1
              done

              echo "Starting task execution" > /task/output.txt 2>&1 || {
                echo "Failed to write to /task/output.txt" >&2
                systemctl poweroff
                exit 1
              }

              if [ -f /task/run.sh ]; then
                chmod +x /task/run.sh
                /bin/sh /task/run.sh >> /task/output.txt 2>&1 || echo "Script exited with code $?" >> /task/output.txt
              else
                echo "Error: /task/run.sh not found" >> /task/output.txt
              fi
              sync  # Ensure output is written
              systemctl poweroff
            '';
          };
        })
      ];
    };

  };
}
