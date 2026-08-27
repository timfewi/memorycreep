# Copy this file outside Git and replace every hardware-specific value.
# The deployment host imports that private replacement during installation.
{ lib, modulesPath, ... }:

{
  imports = [ (modulesPath + "/installer/scan/not-detected.nix") ];

  pentestagent.hardware = {
    hostName = "memorycreep-workstation";
    lanInterface = "enp1s0";
    vpnInterface = "wg0";
  };

  boot.initrd.availableKernelModules = [
    "nvme"
    "xhci_pci"
    "usbhid"
    "uas"
  ];
  boot.kernelModules = [ "kvm-intel" ];
  hardware.cpu.intel.updateMicrocode = lib.mkDefault true;
  hardware.enableRedistributableFirmware = true;
  nixpkgs.hostPlatform = lib.mkDefault "x86_64-linux";
}
