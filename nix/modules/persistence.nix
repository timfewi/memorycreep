{ lib, pkgs, ... }:

{
  boot.initrd = {
    systemd.enable = true;
    supportedFilesystems = [ "btrfs" ];
    systemd.services.rollback-root = {
      description = "Reset the ephemeral root Btrfs subvolume";
      wantedBy = [ "initrd.target" ];
      after = [ "systemd-cryptsetup@cryptroot.service" ];
      before = [ "sysroot.mount" ];
      unitConfig.DefaultDependencies = "no";
      serviceConfig.Type = "oneshot";
      path = [ pkgs.btrfs-progs ];
      script = ''
        mkdir -p /btrfs
        mount -t btrfs -o subvolid=5 /dev/mapper/cryptroot /btrfs
        if [ -e /btrfs/root ]; then
          btrfs subvolume delete /btrfs/root
        fi
        btrfs subvolume create /btrfs/root
        umount /btrfs
      '';
    };
  };

  fileSystems = {
    "/" = {
      device = "/dev/mapper/cryptroot";
      fsType = "btrfs";
      options = [
        "subvol=root"
        "compress=zstd"
        "noatime"
      ];
    };
    "/persist" = {
      device = "/dev/mapper/cryptroot";
      fsType = "btrfs";
      neededForBoot = true;
      options = [
        "subvol=persist"
        "compress=zstd"
        "noatime"
      ];
    };
    "/boot" = {
      device = "/dev/disk/by-partlabel/ESP";
      fsType = "vfat";
      options = [
        "umask=0077"
        "noexec"
        "nodev"
        "nosuid"
      ];
    };
    "/var/lib/pentestagent" = {
      device = "/persist/pentestagent";
      options = [ "bind" ];
      neededForBoot = true;
    };
    "/var/lib/pentestagent-broker" = {
      device = "/persist/broker";
      options = [ "bind" ];
      neededForBoot = true;
    };
    "/var/lib/microvms" = {
      device = "/persist/microvms";
      options = [ "bind" ];
      neededForBoot = true;
    };
    "/var/lib/nixos" = {
      device = "/persist/system/nixos";
      options = [ "bind" ];
      neededForBoot = true;
    };
    "/var/lib/sbctl" = {
      device = "/persist/secureboot";
      options = [ "bind" ];
      neededForBoot = true;
    };
  };

  systemd.tmpfiles.rules = [
    "d /persist/broker 0700 pta-broker pta-broker -"
    "d /persist/identity 0700 root root -"
    "d /persist/keys 0700 root root -"
    "d /persist/microvms 0700 root root -"
    "d /persist/pentestagent 0710 root pta-malware -"
    "d /persist/pentestagent/projects 0700 root root -"
    "d /persist/pentestagent/snapshots 0700 root root -"
    "d /persist/pentestagent/scratch 0710 root pta-malware -"
    "d /persist/pentestagent/windows 0710 root pta-malware -"
    "d /persist/secureboot 0700 root root -"
    "d /persist/system/nixos 0755 root root -"
  ];
}
