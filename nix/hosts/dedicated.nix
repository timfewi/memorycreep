{
  config,
  inputs,
  lib,
  pentestagent,
  pkgs,
  hostTools,
  wasmtime38,
  ...
}:

{
  imports = [
    inputs.microvm.nixosModules.host
    inputs.lanzaboote.nixosModules.lanzaboote
    inputs."sops-nix".nixosModules.sops
    ./hardware-example.nix
    ../modules/hardware-options.nix
    ../modules/hardening.nix
    ../modules/persistence.nix
    ../modules/secure-boot.nix
    ../modules/broker.nix
    ../modules/microvms.nix
    ../modules/malware-lab.nix
  ];

  networking.interfaces.${config.pentestagent.hardware.lanInterface}.useDHCP =
    lib.mkDefault true;

  boot = {
    kernelPackages = pkgs.linuxPackages_hardened;
    initrd.systemd.enable = true;
  };

  virtualisation = {
    libvirtd.enable = false;
    containers.enable = false;
  };

  assertions = [
    {
      assertion =
        config.pentestagent.hardware.lanInterface != config.pentestagent.hardware.vpnInterface;
      message = "LAN and VPN profiles must use distinct declared interfaces";
    }
  ];
}
