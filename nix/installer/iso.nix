{
  lib,
  modulesPath,
  pkgs,
  ...
}:

let
  installer = pkgs.writeShellApplication {
    name = "install-memorycreep-workstation";
    runtimeInputs = with pkgs; [
      btrfs-progs
      cryptsetup
      dosfstools
      gptfdisk
      mkpasswd
      nixos-install-tools
      parted
      sbctl
      systemd
      util-linux
    ];
    text = builtins.readFile ../../scripts/install-host;
  };
in
{
  imports = [
    (modulesPath + "/installer/cd-dvd/installation-cd-minimal.nix")
  ];

  isoImage.isoName = lib.mkForce "memorycreep-nixos-26.05-x86_64.iso";
  nixpkgs.hostPlatform = "x86_64-linux";
  networking = {
    hostName = "pta-installer";
    wireless.enable = false;
  };
  services.openssh.enable = false;
  environment = {
    systemPackages = [
      installer
      pkgs.age
      pkgs.sops
    ];
    etc."pentestagent/source".source = lib.cleanSource ../..;
  };
  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];
  system.stateVersion = "26.05";
}
