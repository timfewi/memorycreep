{
  config,
  inputs,
  lib,
  pentestagent,
  pkgs,
  wasmtime38,
  ...
}:

{
  microvm.vms.pentest = {
    autostart = false;
    inherit pkgs;
    specialArgs = {
      inherit pentestagent wasmtime38;
    };
    config.imports = [ ../guests/pentest.nix ];
  };

  networking.useNetworkd = true;
  systemd.network.networks."40-pta-pentest" = {
    matchConfig.Name = "pta-pentest";
    address = [
      "169.254.77.1/30"
      "fd42:7074:6100::1/64"
    ];
    networkConfig = {
      DHCP = "no";
      IPv6AcceptRA = false;
      LinkLocalAddressing = "no";
    };
    linkConfig.RequiredForOnline = "no";
  };

  boot.kernel.sysctl = {
    "net.ipv4.ip_forward" = 1;
    "net.ipv6.conf.all.forwarding" = 1;
  };

  systemd.services."microvm@pentest".unitConfig = {
    ConditionPathExists = [
      "/run/pentestagent/project.img"
      "/run/pentestagent/guest/session.json"
      "/run/pentestagent/guest/broker-token"
    ];
  };

  systemd.tmpfiles.rules = [
    "d /run/pentestagent 0710 root pta-broker -"
    "d /run/pentestagent/guest 0700 root root -"
    "d /run/pentestagent/overlays 0700 root root -"
  ];
}
