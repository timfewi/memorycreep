{
  symlinkJoin,
  writeShellApplication,
  python312,
  nftables,
  systemd,
  openssh,
  btrfs-progs,
  e2fsprogs,
  coreutils,
  dosfstools,
  iproute2,
  OVMF,
  qemu,
  xorriso,
}:

let
  python = python312.withPackages (
    ps: with ps; [
      aiohttp
      httpx
      typer
    ]
  );

  pta = writeShellApplication {
    name = "pta";
    runtimeInputs = [
      nftables
      systemd
      openssh
    ];
    text = ''
      exec ${python}/bin/python ${../../pentestagent/host_cli.py} "$@"
    '';
  };

  broker = writeShellApplication {
    name = "pentestagent-broker";
    runtimeInputs = [ ];
    text = ''
      exec ${python}/bin/python ${../../pentestagent/broker.py} "$@"
    '';
  };

  malwareLab = writeShellApplication {
    name = "pta-malware-lab";
    runtimeInputs = [
      coreutils
      dosfstools
      e2fsprogs
      iproute2
      qemu
      xorriso
    ];
    text = ''
      export PTA_OVMF_CODE="${OVMF.fd}/FV/OVMF_CODE.fd"
      export PTA_OVMF_VARS="${OVMF.fd}/FV/OVMF_VARS.fd"
      exec ${python}/bin/python ${../../pentestagent/malware_lab.py} "$@"
    '';
  };

  volumeHelper = writeShellApplication {
    name = "pta-volume";
    runtimeInputs = [
      btrfs-progs
      coreutils
      e2fsprogs
    ];
    text = ''
      exec ${python}/bin/python ${../../pentestagent/volume_helper.py} "$@"
    '';
  };
in
symlinkJoin {
  name = "pentestagent-host-tools-0.2.0";
  paths = [
    pta
    broker
    malwareLab
    volumeHelper
  ];
}
