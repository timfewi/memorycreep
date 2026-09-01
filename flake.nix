{
  description = "Hardened MemoryCreep NixOS workstation and isolated guests";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/062346a6d85bc4b49dfaa61c986e9c5be21217d1";

    microvm = {
      url = "github:microvm-nix/microvm.nix/ea57aebfb6016d9f091af7576a97dcf1aaa71fa1";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    lanzaboote = {
      url = "github:nix-community/lanzaboote/69cf334f9dbc11213c6228c97e9b32924d51443f";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    sops-nix = {
      url = "github:Mic92/sops-nix/a8627b21b9107c5711c96b84f32a9a4b3d45295f";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix/4b59abb2ae1896d2a0e1abfc47fbc9bf985ea730";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix/1b1485546d85f6f6c7aadb10c4923dbc09633263";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      microvm,
      ...
    }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
      pentestagent = pkgs.callPackage ./nix/pkgs/pentestagent.nix { };
      hostTools = pkgs.callPackage ./nix/pkgs/host-tools.nix { };
      wasmtime38 = pkgs.callPackage ./nix/pkgs/wasmtime-38.nix { };
      specialArgs = {
        inherit
          hostTools
          inputs
          pentestagent
          wasmtime38
          ;
      };
      mkSystem =
        modules:
        nixpkgs.lib.nixosSystem {
          inherit system specialArgs;
          modules = modules;
        };
      hostSystem = mkSystem [ ./nix/hosts/dedicated.nix ];
      pentestSystem = mkSystem [
        microvm.nixosModules.microvm
        ./nix/guests/pentest.nix
      ];
      controllerSystem = mkSystem [
        microvm.nixosModules.microvm
        ./nix/guests/malware-controller.nix
      ];
      linuxDetonationSystem = mkSystem [
        microvm.nixosModules.microvm
        ./nix/guests/linux-detonation.nix
      ];
      installerSystem = mkSystem [ ./nix/installer/iso.nix ];
      cleanSource = nixpkgs.lib.cleanSource ./.;
    in
    {
      packages.${system} = {
        default = pentestagent;
        inherit hostTools pentestagent;
        memorycreep = pentestagent;
        wasmtime = wasmtime38;
        pentest-vm = pentestSystem.config.microvm.declaredRunner;
        malware-controller-vm = controllerSystem.config.microvm.declaredRunner;
        linux-detonation-vm = linuxDetonationSystem.config.microvm.declaredRunner;
        installer-iso = installerSystem.config.system.build.isoImage;
      };

      nixosConfigurations = {
        memorycreep-workstation = hostSystem;
        memorycreep-guest = pentestSystem;
        pentest-workstation = hostSystem;
        pentest-guest = pentestSystem;
        malware-controller = controllerSystem;
        linux-detonation = linuxDetonationSystem;
        installer = installerSystem;
      };

      checks.${system} = {
        agent-package = pentestagent;
        host = hostSystem.config.system.build.toplevel;
        pentest-vm = pentestSystem.config.microvm.declaredRunner;
        malware-controller-vm = controllerSystem.config.microvm.declaredRunner;
        linux-detonation-vm = linuxDetonationSystem.config.microvm.declaredRunner;

        source-policy = pkgs.runCommand "memorycreep-source-policy" {
          nativeBuildInputs = [
            pkgs.bash
            pkgs.python312
          ];
        } ''
          cp -R ${cleanSource} source
          chmod -R u+w source
          cd source
          ${pkgs.bash}/bin/bash scripts/verify-source
          touch "$out"
        '';

        security-static = pkgs.runCommand "memorycreep-security-static" {
          nativeBuildInputs = [
            pkgs.bash
            pkgs.python312
            pkgs.python312Packages.semgrep
          ];
        } ''
          cp -R ${cleanSource} source
          chmod -R u+w source
          cd source
          ${pkgs.bash}/bin/bash scripts/security-scan static
          touch "$out"
        '';

        python-tests = pkgs.runCommand "memorycreep-python-tests" {
          nativeBuildInputs = [
            pentestagent
            pkgs.python312Packages.pytest
            pkgs.python312Packages.pytest-asyncio
            pkgs.python312Packages.pytest-mock
          ];
        } ''
          cd ${cleanSource}
          pytest -q tests/unit tests/security
          touch "$out"
        '';

        formatting = pkgs.runCommand "memorycreep-formatting" {
          nativeBuildInputs = [
            pkgs.python312Packages.black
            pkgs.findutils
            pkgs.nixfmt-rfc-style
            pkgs.ruff
          ];
        } ''
          cd ${cleanSource}
          black --check pentestagent tests
          ruff check pentestagent tests
          find . -name "*.nix" -print0 | xargs -0 nixfmt --check
          touch "$out"
        '';
      };

      devShells.${system} = {
        default = pkgs.mkShell {
          inputsFrom = [ pentestagent ];
          packages = [
            pkgs.bash
            pkgs.python312Packages.black
            pkgs.findutils
            pkgs.git
            pkgs.nixfmt-rfc-style
            pkgs.python312
            pkgs.python312Packages.pytest
            pkgs.python312Packages.pytest-asyncio
            pkgs.python312Packages.pytest-cov
            pkgs.python312Packages.pytest-mock
            pkgs.ruff
            pkgs.uv
          ];
        };
        security = pkgs.mkShell {
          inputsFrom = [ self.devShells.${system}.default ];
          packages = [
            pkgs.osv-scanner
            pkgs.python312Packages.semgrep
          ];
        };
        all = pkgs.mkShell {
          inputsFrom = [
            self.devShells.${system}.default
            self.devShells.${system}.security
          ];
          packages = [
            pkgs.age
            pkgs.cloud-hypervisor
            pkgs.qemu
            pkgs.sbctl
            pkgs.sops
            wasmtime38
          ];
        };
      };

      formatter.${system} = pkgs.nixfmt-rfc-style;

      lib = {
        pinnedPython = "3.12";
        uv2nixInput = inputs.uv2nix;
        pyprojectNixInput = inputs.pyproject-nix;
      };
    };
}
