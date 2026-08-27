# MemoryCreep repository guide

## Identity and compatibility

The product and repository are named **MemoryCreep**. The preferred application
entry point is `memorycreep`, and the hardened host is controlled with `pta`.
The internal Python package remains `pentestagent`; existing
`pentestagent`, `pentestagent-*`, and `PENTESTAGENT_*` interfaces remain
available for compatibility.

This repository is independently maintained. See `UPSTREAM.md` for provenance
and update policy.

## Prerequisites

The supported product targets x86_64 Linux with UEFI, KVM, at least eight CPU
cores, and 32 GiB RAM. Development uses the pinned Nix flake and Python 3.12.
Do not put provider keys, Secure Boot material, recovery keys, project volumes,
Windows images, or hardware enrollment state in Git or the Nix store.

## Clone and inspect

```bash
git clone https://github.com/timfewi/memorycreep.git
cd memorycreep
git status --short
```

Inspect `.envrc` before using any environment loader. The reproducible shell
can be entered explicitly:

```bash
nix develop .#all
```

## Lightweight verification

Run the repository source gate before every commit:

```bash
bash scripts/verify-source
git diff --check
```

The source gate compiles Python sources and checks pinned inputs, runtime
construction, prohibited container privileges, capability boundaries, broker
persistence, malware-lab isolation, and WASM snapshot enforcement.

Run focused Python checks in the declared environment:

```bash
nix develop .#all --command pytest -q tests/unit tests/security
nix develop .#all --command black --check pentestagent tests
nix develop .#all --command ruff check pentestagent tests
```

Evaluate the flake without building all images:

```bash
nix flake check --no-build
```

## Builds

The following commands can be expensive:

```bash
nix flake check
nix build .#memorycreep
nix build .#pentest-vm
nix build .#malware-controller-vm
nix build .#linux-detonation-vm
nix build .#installer-iso
```

A release is incomplete until `flake.lock` and `uv.lock` are reviewed and
committed, the Python package consumes the intended locked dependency graph,
and every host and guest evaluates and builds successfully.

## Repository layout

```text
pentestagent/               Python implementation and compatibility package
pentestagent/runtime/       runtime abstraction, policy, approvals, audit
pentestagent/interface/     CLI and Textual TUI
nix/hosts/                  hardened host declarations
nix/guests/                 pentest and malware MicroVM guests
nix/modules/                host firewall, broker, persistence, VM services
nix/pkgs/                   application and pinned Wasmtime packages
nix/installer/              installer ISO declaration
tests/security/             policy and confidentiality tests
docs/nixos-workstation.md   deployment, recovery, and acceptance guide
scripts/verify-source       lightweight source gate
```

## Hardened host workflow

After installation, create one locally confirmed session at a time:

```bash
sudo pta status

sudo pta start pentest \
  --project customer-a \
  --scope 192.0.2.0/24 \
  --net offline

sudo pta start malware \
  --guest linux \
  --sample /path/to/sample

sudo pta export --project malware-quarantine
sudo pta stop
```

Only test systems for which you have explicit written authorization. The host
firewall, not an LLM response or shell parser, is the final network scope
boundary.

## Changes and releases

1. Work on a focused branch.
2. Review `git status` and the complete diff.
3. Run the source gate and focused tests.
4. Run full Nix checks and image builds before a release.
5. Perform the hardware acceptance sequence in
   `docs/nixos-workstation.md`.
6. Tag and publish only artifacts built from reviewed lockfiles.

Upstream is observation-only. Review upstream changes with `git fetch upstream`
and cherry-pick individual audited fixes; do not automatically merge
`upstream/main`.
