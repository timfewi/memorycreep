# MemoryCreep-NixOS deployment and recovery

This repository now defines the hardened product boundary. The ordinary Python
and Docker entry points remain development/legacy interfaces; they are not the
dedicated-host security boundary.

## Trust boundaries

The host contains only the launcher, nftables policy, encrypted persistent
state, the cloud-key broker, and VM launchers. MemoryCreep and native security
tools are present only in the Pentest MicroVM. The malware controller and its
detonation guest use a separate bridge with no host address and no uplink.

The language model is not a security principal. Python policy gives fast,
operator-visible denials, while the host nftables table is the final network
boundary. Every accepted target is an IP/CIDR confirmed locally. Hostnames are
resolved once at session creation, displayed, written into the guest
`/etc/hosts`, and represented in nftables only by those pinned A/AAAA
addresses.

The host does not mount a user's home directory, a Docker socket, or another
project into a VM. One selected ext4 project image is attached as a VirtIO block
volume. Before reuse, its containing Btrfs subvolume is snapshotted read-only.
The Nix store is immutable and the writable store/root overlay lives below
`/run`, so it disappears when `pta stop` removes the session.

## Reproducible build

All flake inputs use immutable 40-character revisions. Nixpkgs is the NixOS
26.05 branch revision selected by the project; MicroVM.nix, Lanzaboote,
sops-nix, uv2nix, and pyproject.nix are independently revision-pinned. The
Python application uses Python 3.12 and a dependency closure fixed by that
nixpkgs revision. Direct Python requirements are exact pins. Wasmtime 38.0.4
uses fixed source and Cargo vendor hashes.

Run in the declared shell:

```bash
nix flake lock
nix flake check
nix build .#memorycreep
nix build .#pentest-vm
nix build .#malware-controller-vm
nix build .#linux-detonation-vm
nix build .#installer-iso
```

Review and commit the generated `flake.lock` before using a release artifact.
Do not update only one input casually: rebuild every check and both guest
runners after any input change.

## Hardware declaration

Copy `nix/hosts/hardware-example.nix` to a private deployment checkout and
replace the interface names, CPU module, and initrd modules. The LAN and VPN
interfaces must be different. `pta` refuses an online profile that lacks an
explicit interface in `/etc/pentestagent/network.json`.

The reference hardware is x86_64 with UEFI, KVM, at least eight CPU cores,
32 GiB RAM, and enough encrypted storage for 64-GiB sparse project volumes.
Only one large detonation or pentest guest should run at a time.

## Secrets

Create an age identity on offline-controlled media. Encrypt a sops document
with these keys:

```yaml
openai-api-key: ENC[AES256_GCM,...]
tavily-api-key: ENC[AES256_GCM,...]
sops:
  age: [...]
```

The installer copies the identity to `/persist/keys/sops-age` and the
encrypted document to `/persist/secrets/providers.yaml`. sops-nix materializes
credentials below `/run/secrets` for the broker user. Provider credentials are
never copied to guest metadata. A separate random bearer token exists only for
one VM session, is read from a mode-0400 runtime file, and is passed directly to
broker clients rather than placed in the process or tool-child environment.

Broker provider/model, request-size, token, rate, and estimated daily-cost
limits are declared in `nix/modules/broker.nix`. Metadata-only rate and
cost counters are atomically stored on the encrypted host so restarting a VM
or the broker cannot reset a daily budget. Broker logs use a strict metadata
allowlist; prompts, response bodies, commands, and credentials are not logged. The broker binds only to the Pentest TAP address and accepts only
the guest's fixed source IP plus its one-session bearer token.

## Installation

Building `.#installer-iso` produces a minimal UEFI image containing this
source tree and `install-memorycreep-workstation`. Boot it with Secure Boot
temporarily disabled. Prepare a second, separately tested recovery medium and
two offline copies of the LUKS recovery key before replacing the workstation.

The installer is intentionally destructive and requires the exact target block
device to be typed back:

```bash
sudo install-memorycreep-workstation \
  --disk /dev/nvme0n1 \
  --flake /etc/pentestagent/source \
  --age-key /run/media/operator/KEYS/sops-age \
  --providers /run/media/operator/KEYS/providers.yaml
```

It creates GPT, a 1-GiB ESP, LUKS2, and Btrfs `root`/`persist`
subvolumes; enrolls a FIDO2 token and a separate recovery key; creates a local
yescrypt password hash; generates Secure Boot keys; and installs the dedicated
configuration. No disk swap is created. The installed system uses ZRAM.

On first boot, test both FIDO2 unlock and the recovery key before enrollment.
Then enter firmware Setup Mode and run locally:

```bash
sudo sbctl enroll-keys --microsoft
sudo nixos-rebuild boot --flake /path/to/reviewed/source#memorycreep-workstation
sudo sbctl verify
```

Never enroll keys before a recovery boot and recovery-key unlock have both
succeeded. Secure Boot keys, the age identity, password hash, FIDO2 enrollment
records, logs, images, and volumes remain below encrypted `/persist` or on
offline media, never in Git or the Nix store.

The root Btrfs subvolume is recreated in initrd on each boot. Only identity,
Secure Boot/sops material, NixOS identity, VM state, project vaults, and malware
scratch state use explicit persistent bind mounts.

## Pentest sessions

```bash
sudo pta start pentest \
  --project customer-a \
  --scope 192.0.2.0/24 \
  --scope app.customer.example \
  --net offline
```

The confirmation screen shows project, requested scope, pinned DNS answers,
network profile, fixed 8-vCPU/16-GiB resources, and broker limits. The
`offline` profile permits the local broker but no target forwarding. `vpn`
and `lan` install target-specific forwarding and NAT rules bound to their
declared uplink. The later default-deny host chains accept only packets carrying
the session mark. Changing a source address, raw shell, IPv6, DNS rebinding, or
a crew worker cannot add a firewall target.

The guest operator and TUI run without root. Their systemd unit grants only
the ambient `CAP_NET_RAW` and `CAP_NET_ADMIN` capabilities required by
native scanners; its bounding set removes every other capability and
`NoNewPrivileges` prevents later privilege gains. Chromium may create its
sandbox namespaces except cgroup namespaces. These guest permissions do not
widen the host-enforced scope.

By default, `pta start` attaches the local Cloud-Hypervisor console. Use
`--detach` only for automation. Useful TUI commands are:

- `/scope`: immutable host-confirmed scope
- `/approvals`: pending/settled high-risk decisions
- `/approvals approve ID` and `/approvals deny ID`
- `/network`: active profile and scope boundary
- `/vm-status`: policy and backend status

Recon and active enumeration inside scope proceed automatically. Exploitation,
credential attacks, persistence, and denial-of-service operations create a
one-use approval bound to the exact tool, risk, targets, and argument digest.
A denial never reaches the runtime. Terminal calls must declare risk, purpose,
targets, and input/output paths; opaque shell constructs are conservatively
escalated. Crew workers share the exact same `PolicyRuntime`, scope, approval
store, and audit chain. The guest verifies the complete hash chain before
resuming it; both the root-owned audit directory and session file are marked
append-only. A malformed, replaced, or symlinked audit path fails closed.

Stop a session with `sudo pta stop`. This stops the broker first-class unit,
removes nftables state, deletes the writable overlay and bearer token, and
leaves the selected project volume plus its versioned snapshot.

## WASI components

Wasmtime is an additional plugin boundary, not a replacement for the MicroVM.
Nmap, Metasploit, browsers, and other native tools stay native in the Pentest
guest. The component runner accepts only parser, normalizer,
report-transformation, and small-plugin purposes.

The default allowlist is empty. Add a reviewed component by building a new
declarative guest configuration with a record of this shape:

```json
{
  "components": {
    "<lowercase sha256>": {
      "name": "sarif-normalizer",
      "purpose": "normalizer",
      "signature": "review-record-or-detached-signature-reference"
    }
  }
}
```

The hash is authoritative. The runner copies the exact bytes it hashes into a
write-sealed memfd and executes that descriptor, so a path swap cannot replace
an approved component. Input directories and every contained entry must be
read-only; output is a separate writable directory. Symlinks are rejected, and
both directory capabilities are held by descriptor before Wasmtime starts.
Wasmtime receives no inherited environment or sockets and is given only
`/input` and `/output` preopens. Fuel, epoch deadline, component size, memory,
instance, table, memory-count, table-element, wall-clock, and streaming output
limits apply.

## Malware lab

`pta start malware` copies and re-hashes the confirmed sample before producing
a read-only ISO. The controller and detonation TAPs join `pta-lab`, a bridge
with no IP, route, DHCP, DNS, or uplink. Neither guest contains the broker or a
project volume. A separate FAT scratch image records opaque results. After the
detonation guests have stopped, the host lists its size/hash and requests local
confirmation. `pta export` first creates or versions the selected Btrfs project
vault, then atomically stores the sparse image below
`malware-exports/<session>/opaque/`; it is not mounted into another running VM.

Linux uses an immutable NixOS guest and a fresh writable-store overlay in
`/run`. The sample runs as an unprivileged user with a five-minute limit.
The controller capture process also runs unprivileged, with only raw-packet
capabilities, and writes to the noexec scratch filesystem. In addition to the
bridge having no address or uplink, the host firewall drops all input, output,
and forwarding on every malware-lab interface before established-flow and ICMP
rules.

Windows uses a fresh qcow2 overlay. Copy
`nix/config/windows-manifest.example.json` to
`/var/lib/pentestagent/windows/manifest.json`, supply a separately licensed
qcow2 golden image, set its lowercase SHA-256, and make the directory
root:`pta-malware` with no write access for that group. Configure the golden
guest with static address `10.77.0.2/24`; it must have no default gateway,
clipboard integration, shared folders, USB passthrough, host agents, or
automatic cloud synchronization.

Every stop removes the sample ISO, firmware-variable copy, TAP, and Linux or
Windows overlay. Scratch remains only long enough for `pta export`, which
copies opaque files into one explicitly selected project. Malware sessions have
no cloud path; this is stricter than prompt-by-prompt cloud confirmation and
ensures binaries and extracted content never reach a provider.

## Acceptance sequence

After source checks, perform hardware-backed tests in this order:

1. Boot installer and recovery media without touching the production disk.
2. Test FIDO2 and recovery-key unlock independently.
3. Verify Secure Boot signatures and a tampered-kernel rejection.
4. Start an offline Pentest session; verify target traffic is absent.
5. In a controlled test network, attempt in-scope and out-of-scope IPv4/IPv6,
   raw-shell, alternate-DNS, rebinding, and crew-worker traffic.
6. Reboot the VM; verify its overlay vanished and the selected project survived.
7. Run Linux and Windows benign canary samples; verify neither guest reaches
   Internet, host, project vault, nor broker, and both overlays disappear.
8. Enable VPN and LAN profiles only after the preceding checks pass.

`scripts/verify-source` performs dependency/pinning, prohibited-container,
runtime-construction, version, and Python syntax checks. `nix flake check`
adds formatting, unit/security tests, host evaluation, and reproducible guest
runner builds. Secure Boot, FIDO2, KVM networking, and Windows licensing/image
tests require the actual deployment hardware and cannot be certified by a
source-only build.
