# Code- und Supply-Chain-Prüfung

Diese Prüfungen sind ein **Release-Gate**, kein mathematischer Beweis dafür, dass
der Quellcode frei von Malware ist. Sie kombinieren reproduzierbare Tests,
lokale statische Regeln, bekannte Schwachstellen in Abhängigkeiten und eine
Prüfung auf veränderliche beziehungsweise opaque Build-Eingaben. Für hohe
Sicherheit bleiben Quellcode-Review, Herkunftsprüfung und Ausführung in einer
frischen, geheimnisfreien VM notwendig.

## Schnellstart

Nach dem bereits bestätigten `.envrc`-Load stellt die Flake alle Werkzeuge
bereit. Nach dieser Änderung die Umgebung einmal neu laden und die Werkzeuge
prüfen:

```bash
direnv reload
for tool in python pytest black ruff nixfmt semgrep osv-scanner nix; do
  command -v "$tool" || printf 'FEHLT: %s\n' "$tool"
done
```

Der normale, nicht image-bauende Lauf ist:

```bash
bash scripts/test-e2e quick
```

Er führt ohne OSV-Netzwerkzugriff aus:

1. `scripts/verify-source` und Python-Kompilierung,
2. den Source-/Binary-Audit für Symlinks, ausführbare Dateien,
   Trojan-Source-Zeichen und die SHA-256-Allowlist,
3. Semgrep mit ausschließlich `security/semgrep.yml`,
4. Black, Ruff und Nix-Formatprüfung,
5. Unit- und Security-Tests,
6. `nix flake check --no-build` zur Evaluation aller Flake-Ausgaben.

Der strengere Lauf ergänzt Integrationstests, Lockfile-Konsistenz,
Supply-Chain-Provenienz und OSV:

```bash
bash scripts/test-e2e security
```

Der vollständige Build kann mehrere GiB übertragen und VM-/ISO-Images bauen:

```bash
bash scripts/test-e2e full
```

Dieser Lauf baut die deklarierte Flake, bootet aber keine Gäste und detoniert
keine Samples. Boot-, Firewall-, Secure-Boot-, LUKS/FIDO2- und
Malware-Lab-Abnahmetests brauchen weiterhin eine dedizierte Testmaschine.

## Einzelne Prüfungen

```bash
# Leichte, netzwerkfreie Source- und Policy-Prüfung
bash scripts/verify-source

# Alle Python-Tests
python -m pytest -q tests

# Format und Lint
black --check pentestagent tests
ruff check pentestagent tests
find . -path ./.direnv -prune -o -path ./.git -prune -o -name '*.nix' -print0 \
  | xargs -0 nixfmt --check

# Source-/Binary-Audit plus Semgrep; keine Registry-Regeln oder Telemetrie
bash scripts/security-scan static

# Supply-Chain-Audit plus OSV; online werden nur Paketkoordinaten abgefragt
bash scripts/security-scan dependencies

# Alternativ mit einer vorher vertrauenswürdig befüllten lokalen OSV-Datenbank
OSV_OFFLINE=1 \
OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY=/pfad/zur/osv-datenbank \
  bash scripts/security-scan dependencies

# Alle Security-Prüfungen
bash scripts/security-scan all

# Nur Nix-Auswertung oder kompletter Build
nix flake check --no-build
nix flake check --print-build-logs
```

## Python-Lockfile einmalig erzeugen

OSV darf erst grün werden, wenn der vollständige transitive Python-Graph
aufgelöst und reviewt wurde:

```bash
nix develop .#security
uv lock
uv lock --check
git diff -- pyproject.toml uv.lock
bash scripts/security-scan dependencies
```

Neue Dateien sind bei Git-basierten Flakes erst nach dem Staging Bestandteil
der Flake-Quelle. Vor einem Nix-Check daher mindestens den beabsichtigten
Dateisatz mit `git status --short` prüfen und die neuen Security-Dateien
stagen. Das Lockfile enthält Artefakt-Hashes, ersetzt aber keine Prüfung der
Paket-Herkunft.

OSV versteht den Python-Lockgraphen und weitere unterstützte Lockfiles, aber
nicht automatisch die vollständige Nix-Store-Closure. `flake.lock` fixiert
deren Quellen; die eigentliche Closure wird erst durch den Nix-Build belegt.
Diese beiden Evidenzarten dürfen nicht miteinander verwechselt werden.

Zum Mitschreiben, ohne den Exit-Code der Prüfung zu verlieren:

```bash
mkdir -p security-reports
set -o pipefail
bash scripts/test-e2e quick 2>&1 | tee security-reports/e2e.log
```

`security-reports/` ist absichtlich Git-ignoriert, weil Scanner-Ausgaben
Quelltextausschnitte oder Paketnamen enthalten können.

## Was die Security-Gates erzwingen

- GitHub Actions müssen auf einen vollständigen 40-stelligen Commit zeigen.
- Container-Basisimages und Container-Actions müssen per SHA-256-Digest
  unveränderlich sein.
- PyPI-Anforderungen benötigen exakte Versionen und dürfen sich zwischen
  Basispaket und Extra nicht widersprechen.
- `uv.lock` und `flake.lock` müssen vorhanden sein.
- Reviewte, nicht ausführbare Binär-Assets sind in
  `security/binary-assets.sha256` inventarisiert; unbekannte oder veränderte
  Binärdateien sowie opaque ELF-, PE- und WASM-Payloads werden blockiert.
- Unerwartete ausführbare Dateien, entweichende Symlinks,
  Unicode-Bidi-Steuerzeichen und übergroße Dateien werden gemeldet.
- Mutable Paketinstallationen in Dockerfiles werden blockiert.
- Semgrep blockiert unter anderem dynamische Codeausführung, unsichere
  Deserialisierung, Shell-Bypässe, deaktivierte TLS-Prüfung,
  Download-zu-Interpreter-Pipelines und hochkonfidente Schlüssel-Muster.
- Persistierte RAG-Indizes verwenden validiertes, größenbegrenztes JSON.
  Frühere `index.pkl`-Caches werden absichtlich nicht mehr geladen und bei der
  nächsten Indexierung durch `index.json` ersetzt.

Semgrep lädt keine Regeln aus dem Internet: Die geprüfte Policy liegt vollständig
in `security/semgrep.yml`; Metriken und Versionsprüfung sind abgeschaltet.
OSV-Scanner benötigt dagegen aktuelle Schwachstellendaten. Im Standardmodus
werden erkannte Paketkoordinaten und Versionen beim öffentlichen OSV-Dienst
abgefragt. Der Offline-Modus verwendet ausschließlich eine bereits vorhandene,
separat vertrauenswürdig bezogene Datenbank und lädt sie nie automatisch.
OSV-Call-Analysis bleibt deaktiviert, weil sie Buildskripte ausführen kann.

## Vor dem ersten Ausführen fremder Repository-Inhalte

Führe den ersten Scan in einer frischen VM ohne API-Schlüssel, SSH-Agent,
Browserprofil, Projekt-Mounts oder Schreibzugriff auf andere Repositories aus.
Prüfe zunächst die Dateien, die den Scan selbst definieren:

```bash
git status --short
git diff -- scripts/audit-supply-chain scripts/security-scan scripts/test-e2e
git diff -- security/semgrep.yml flake.nix
git diff --cached
git log --show-signature --oneline --decorate -20
```

Danach sollten besonders Entrypoints, Installationsskripte, Workflows,
Dockerfiles, Nix-Fetcher, dynamische Imports und Deserialisierung manuell
reviewt werden. Ein grüner Scanner kann absichtlich verschleierten Code,
Zero-Day-Schwachstellen, kompromittierte aber noch nicht bekannte Releases oder
bösartige Logik in legitimen Abhängigkeiten übersehen.

## Bekannte aktuelle Release-Blocker

Beim Stand, auf dem dieses Gate eingeführt wurde, sind mindestens folgende
Findings zu erwarten:

- `uv.lock` fehlt, daher ist der transitive PyPI-Graph nicht eingefroren.
- Die Legacy-Dockerfiles lösen APT-, Pip- und Playwright-Inhalte weiterhin aus
  veränderlichen Quellen auf; das Beispiel unter
  `mcp_examples/stdio/kali/Dockerfile` besitzt außerdem noch keine
  digest-gepinnte Basis.
Diese Meldungen sollten behoben werden. Eine Ausnahme oder Unterdrückung braucht
eine konkrete Bedrohungsanalyse, einen Eigentümer und ein Ablaufdatum.

## CI

`.github/workflows/security.yml` führt den netzwerkfreien Quick-Gate für Pull
Requests und Änderungen auf `main` aus. Die zwei von ihm verwendeten Actions
sind selbst auf volle Commits gepinnt. Ein grüner Quick-Job ist noch keine
Release-Freigabe: Vor einem Release müssen zusätzlich
`bash scripts/test-e2e security` und anschließend der schwere
`bash scripts/test-e2e full` erfolgreich sein. Der Legacy-Docker-Workflow
besitzt zusätzlich einen strengen Preflight und veröffentlicht keine Images,
solange Lockfile- oder Mutable-Input-Findings offen sind.
