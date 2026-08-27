{
  config,
  lib,
  pkgs,
  hostTools,
  ...
}:

{
  boot = {
    tmp.cleanOnBoot = true;
    kernel.sysctl = {
      "kernel.kptr_restrict" = 2;
      "kernel.dmesg_restrict" = 1;
      "kernel.unprivileged_bpf_disabled" = 1;
      "kernel.yama.ptrace_scope" = 2;
      "fs.protected_fifos" = 2;
      "fs.protected_regular" = 2;
      "fs.protected_hardlinks" = 1;
      "fs.protected_symlinks" = 1;
      "net.ipv4.conf.all.accept_redirects" = 0;
      "net.ipv4.conf.all.send_redirects" = 0;
      "net.ipv6.conf.all.accept_redirects" = 0;
    };
    kernelParams = [
      "lockdown=confidentiality"
      "module.sig_enforce=1"
      "slab_nomerge"
      "init_on_alloc=1"
      "init_on_free=1"
      "page_alloc.shuffle=1"
      "randomize_kstack_offset=on"
    ];
  };

  zramSwap = {
    enable = true;
    memoryPercent = 50;
  };
  swapDevices = [ ];

  networking = {
    useDHCP = false;
    firewall.enable = false;
    nftables = {
      enable = true;
      ruleset = ''
        table inet host_filter {
          chain input {
            type filter hook input priority 0; policy drop;
            iifname "lo" accept
            iifname { "pta-lab", "pta-lab-ctrl", "pta-lab-linux", "pta-lab-windows" } drop
            ct state established,related accept
            meta mark 0x505441 accept
            ip protocol icmp accept
            ip6 nexthdr ipv6-icmp accept
            udp sport 67 udp dport 68 accept
            udp sport 547 udp dport 546 accept
          }
          chain forward {
            type filter hook forward priority 0; policy drop;
            iifname { "pta-lab", "pta-lab-ctrl", "pta-lab-linux", "pta-lab-windows" } drop
            oifname { "pta-lab", "pta-lab-ctrl", "pta-lab-linux", "pta-lab-windows" } drop
            ct state established,related accept
            meta mark 0x505441 accept
          }
          chain output {
            type filter hook output priority 0; policy drop;
            oifname "lo" accept
            oifname { "pta-lab", "pta-lab-ctrl", "pta-lab-linux", "pta-lab-windows" } drop
            ct state established,related accept
            ip protocol icmp accept
            ip6 nexthdr ipv6-icmp accept
            udp dport { 53, 67, 123, 51820 } accept
            udp sport 68 udp dport 67 accept
            tcp dport { 53, 80, 443 } accept
          }
        }
      '';
    };
  };

  services = {
    openssh.enable = false;
    avahi.enable = false;
    printing.enable = false;
    resolved.enable = true;
    dbus.implementation = "broker";
    greetd = {
      enable = true;
      settings.default_session = {
        command = "${pkgs.greetd.tuigreet}/bin/tuigreet --cmd sway";
        user = "greeter";
      };
    };
  };

  programs.sway.enable = true;
  hardware.bluetooth.enable = false;
  virtualisation = {
    docker.enable = false;
    podman.enable = false;
  };

  security = {
    sudo.wheelNeedsPassword = true;
    protectKernelImage = true;
    forcePageTableIsolation = true;
    allowSimultaneousMultithreading = false;
  };

  users = {
    mutableUsers = false;
    users = {
      root.hashedPassword = "!";
      operator = {
        isNormalUser = true;
        extraGroups = [ "wheel" ];
        hashedPasswordFile = "/persist/identity/operator-password-hash";
      };
    };
  };

  environment.systemPackages = [
    hostTools
    pkgs.foot
    pkgs.nftables
    pkgs.btrfs-progs
    pkgs.e2fsprogs
  ];

  nix = {
    settings = {
      allowed-users = [
        "root"
        "operator"
      ];
      trusted-users = [ "root" ];
      sandbox = true;
    };
    channel.enable = false;
  };

  systemd.coredump.enable = false;
  system.stateVersion = "26.05";
  time.timeZone = "UTC";
}
