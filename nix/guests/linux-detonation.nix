{ config, lib, pkgs, ... }:

let
  guestMac = "02:50:54:00:10:02";
in
{
  microvm = {
    hypervisor = "cloud-hypervisor";
    vcpu = 4;
    mem = 8192;
    interfaces = [
      {
        type = "tap";
        id = "pta-lab-linux";
        mac = guestMac;
      }
    ];
    shares = [
      {
        tag = "ro-store";
        source = "/nix/store";
        mountPoint = "/nix/.ro-store";
        proto = "virtiofs";
      }
    ];
    writableStoreOverlay = "/nix/.rw-store";
    volumes = [
      {
        image = "/run/pta-malware/current/sample.iso";
        mountPoint = "/sample";
        size = 2048;
        fsType = "iso9660";
      }
      {
        image = "/run/pta-malware/current/linux-overlay.ext4";
        mountPoint = config.microvm.writableStoreOverlay;
        size = 8192;
      }
    ];
  };

  networking = {
    hostName = "pta-linux-detonation";
    useDHCP = false;
    firewall.enable = false;
    nftables = {
      enable = true;
      ruleset = ''
        table inet detonation_filter {
          chain input {
            type filter hook input priority 0; policy drop;
            iifname "lo" accept
            ct state established,related accept
            ip saddr 10.77.0.1 accept
          }
          chain forward {
            type filter hook forward priority 0; policy drop;
          }
          chain output {
            type filter hook output priority 0; policy drop;
            oifname "lo" accept
            ct state established,related accept
            ip daddr 10.77.0.1 accept
          }
        }
      '';
    };
  };

  systemd.network = {
    enable = true;
    networks."10-malware-lab" = {
      matchConfig.MACAddress = guestMac;
      address = [ "10.77.0.2/24" ];
      networkConfig = {
        DHCP = "no";
        IPv6AcceptRA = false;
        LinkLocalAddressing = "no";
      };
    };
  };

  services = {
    resolved.enable = false;
    openssh.enable = false;
    avahi.enable = false;
  };
  users = {
    mutableUsers = false;
    users = {
      root.hashedPassword = "!";
      detonator = {
        isNormalUser = true;
        uid = 1000;
        group = "detonator";
        hashedPassword = "!";
      };
    };
    groups.detonator.gid = 1000;
  };
  fileSystems."/sample".options = lib.mkAfter [
    "ro"
    "nodev"
    "nosuid"
  ];
  environment.systemPackages = with pkgs; [
    file
    strace
    gdb
    tcpdump
    yara
  ];

  systemd.services.detonate-sample = {
    description = "Execute the confirmed sample in the disposable Linux guest";
    wantedBy = [ "multi-user.target" ];
    after = [ "local-fs.target" "network.target" ];
    serviceConfig = {
      Type = "oneshot";
      User = "detonator";
      Group = "detonator";
      WorkingDirectory = "/tmp";
      ExecStart = "${pkgs.writeShellScript "detonate-sample" ''
        set -eu
        ${pkgs.coreutils}/bin/install -m 0500 /sample/sample.bin /tmp/sample.bin
        exec ${pkgs.coreutils}/bin/timeout --signal=KILL 5m /tmp/sample.bin
      ''}";
      StandardOutput = "journal";
      StandardError = "journal";
      NoNewPrivileges = true;
      AmbientCapabilities = [ ];
      CapabilityBoundingSet = [ ];
      PrivateDevices = true;
      ProtectHome = true;
      ProtectKernelLogs = true;
      ProtectKernelModules = true;
      ProtectKernelTunables = true;
      RestrictNamespaces = true;
      RestrictRealtime = true;
      RestrictSUIDSGID = true;
      KillMode = "control-group";
      RuntimeMaxSec = "6min";
      TimeoutStopSec = 10;
      TasksMax = 4096;
      MemoryMax = "6G";
      CPUQuota = "350%";
      LimitCORE = 0;
    };
  };

  boot.kernel.sysctl = {
    "kernel.unprivileged_bpf_disabled" = 1;
    "kernel.kptr_restrict" = 2;
    "kernel.dmesg_restrict" = 1;
  };
  system.stateVersion = "26.05";
}
