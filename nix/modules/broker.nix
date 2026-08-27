{
  config,
  lib,
  pkgs,
  hostTools,
  ...
}:

let
  brokerConfig = pkgs.formats.json { };
  brokerConfigFile = brokerConfig.generate "pentestagent-broker.json" {
    listen_host = "169.254.77.1";
    listen_port = 17443;
    allowed_client_ips = [ "169.254.77.2" ];
    session_token_file = "/run/pentestagent/broker-token";
    usage_state_file = "/var/lib/pentestagent-broker/usage.json";
    request_timeout_seconds = 120;
    providers = {
      openai = {
        kind = "openai";
        base_url = "https://api.openai.com";
        key_file = config.sops.secrets.openai-api-key.path;
        models = [
          "gpt-5"
          "gpt-5-mini"
        ];
        limits = {
          requests_per_minute = 30;
          max_request_bytes = 1000000;
          max_response_bytes = 16000000;
          max_input_tokens = 64000;
          max_output_tokens = 8192;
          daily_cost_usd = 25.0;
          input_cost_per_million = 1.25;
          output_cost_per_million = 10.0;
        };
      };
      tavily = {
        kind = "tavily";
        base_url = "https://api.tavily.com";
        key_file = config.sops.secrets.tavily-api-key.path;
        models = [ "web-search" ];
        key_header = "Authorization";
        key_prefix = "Bearer ";
        limits = {
          requests_per_minute = 10;
          max_request_bytes = 65536;
          max_response_bytes = 4000000;
          max_input_tokens = 4096;
          max_output_tokens = 4096;
          daily_cost_usd = 5.0;
          cost_per_request_usd = 0.01;
        };
      };
    };
  };
in
{
  users = {
    groups.pta-broker = { };
    users.pta-broker = {
      isSystemUser = true;
      group = "pta-broker";
    };
  };

  sops = {
    validateSopsFiles = false;
    useSystemdActivation = true;
    age.keyFile = "/persist/keys/sops-age";
    secrets = {
      openai-api-key = {
        sopsFile = "/persist/secrets/providers.yaml";
        owner = config.users.users.pta-broker.name;
        group = config.users.users.pta-broker.group;
        mode = "0400";
      };
      tavily-api-key = {
        sopsFile = "/persist/secrets/providers.yaml";
        owner = config.users.users.pta-broker.name;
        group = config.users.users.pta-broker.group;
        mode = "0400";
      };
    };
  };

  environment.etc."pentestagent/broker.json".source = brokerConfigFile;

  systemd.services.pentestagent-broker = {
    description = "Session-scoped MemoryCreep cloud key broker";
    partOf = [ "microvm@pentest.service" ];
    after = [
      "network-online.target"
      "sops-nix.service"
    ];
    wants = [ "network-online.target" ];
    serviceConfig = {
      Type = "simple";
      User = "pta-broker";
      Group = "pta-broker";
      ExecStart = "${hostTools}/bin/pentestagent-broker --config /etc/pentestagent/broker.json";
      Restart = "on-failure";
      RestartSec = 2;
      NoNewPrivileges = true;
      PrivateDevices = true;
      PrivateTmp = true;
      ProtectClock = true;
      ProtectControlGroups = true;
      ProtectHome = true;
      ProtectHostname = true;
      ProtectKernelLogs = true;
      ProtectKernelModules = true;
      ProtectKernelTunables = true;
      ProtectProc = "invisible";
      ProtectSystem = "strict";
      RestrictAddressFamilies = [
        "AF_INET"
        "AF_INET6"
      ];
      RestrictNamespaces = true;
      RestrictRealtime = true;
      RestrictSUIDSGID = true;
      SystemCallArchitectures = "native";
      SystemCallFilter = [
        "@system-service"
        "~@mount"
        "~@privileged"
        "~@resources"
      ];
      LockPersonality = true;
      MemoryDenyWriteExecute = true;
      UMask = "0077";
      ReadOnlyPaths = [
        config.sops.secrets.openai-api-key.path
        config.sops.secrets.tavily-api-key.path
        "/run/pentestagent/broker-token"
      ];
      ReadWritePaths = [ "/var/lib/pentestagent-broker" ];
    };
  };
}
