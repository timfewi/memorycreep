{ config, lib, pkgs, ... }:

let
  cfg = config.pentestagent.hardware;
  networkConfig = pkgs.formats.json { };
in
{
  options.pentestagent.hardware = {
    lanInterface = lib.mkOption {
      type = lib.types.str;
      example = "enp1s0";
      description = "Dedicated physical interface used by the confirmed LAN profile.";
    };
    vpnInterface = lib.mkOption {
      type = lib.types.str;
      example = "wg0";
      description = "Dedicated WireGuard/TUN interface used by the confirmed VPN profile.";
    };
    hostName = lib.mkOption {
      type = lib.types.str;
      default = "memorycreep-workstation";
    };
  };

  config = {
    networking.hostName = cfg.hostName;
    environment.etc."pentestagent/network.json".source =
      networkConfig.generate "pentestagent-network.json" {
        lan_interface = cfg.lanInterface;
        vpn_interface = cfg.vpnInterface;
      };
  };
}
