{ lib, pkgs, ... }:

{
  boot.loader = {
    systemd-boot.enable = lib.mkForce false;
    efi.canTouchEfiVariables = true;
  };

  boot.lanzaboote = {
    enable = true;
    pkiBundle = "/var/lib/sbctl";
  };

  boot.initrd.luks.devices.cryptroot = {
    device = "/dev/disk/by-partlabel/cryptroot";
    allowDiscards = false;
    crypttabExtraOpts = [
      "fido2-device=auto"
      "token-timeout=15"
      "headless=no"
    ];
  };

  environment.systemPackages = [
    pkgs.sbctl
    pkgs.systemd
  ];
}
