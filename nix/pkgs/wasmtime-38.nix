{
  lib,
  rustPlatform,
  fetchFromGitHub,
  cmake,
  installShellFiles,
  versionCheckHook,
}:

rustPlatform.buildRustPackage rec {
  pname = "wasmtime";
  version = "38.0.4";

  src = fetchFromGitHub {
    owner = "bytecodealliance";
    repo = "wasmtime";
    tag = "v${version}";
    hash = "sha256-6w4r74s3wtDisCVMu81FALnlmVnfONGM5xVkYYWrLFk=";
    fetchSubmodules = true;
  };

  cargoHash = "sha256-0YN8O8tSAIuw61IIbTHUZpFjP6HjrwMcd7DN2WCQM0s=";
  cargoBuildFlags = [
    "--package"
    "wasmtime-cli"
  ];

  auditable = false;
  nativeBuildInputs = [
    cmake
    installShellFiles
  ];

  doCheck = false;
  nativeInstallCheckInputs = [ versionCheckHook ];
  versionCheckProgramArg = "--version";
  doInstallCheck = true;

  postInstall = ''
    installShellCompletion --cmd wasmtime       --bash <("$out/bin/wasmtime" completion bash)       --zsh <("$out/bin/wasmtime" completion zsh)       --fish <("$out/bin/wasmtime" completion fish)
  '';

  meta = {
    description = "Pinned Wasmtime v38 capability runtime";
    homepage = "https://wasmtime.dev/";
    license = [
      lib.licenses.asl20
      lib.licenses.llvm-exception
    ];
    mainProgram = "wasmtime";
    platforms = lib.platforms.linux;
  };
}
