"""Behavioral tests for the repository structural source audit."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def _audit_fixture(tmp_path: Path) -> Path:
    scripts = tmp_path / "scripts"
    security = tmp_path / "security"
    scripts.mkdir()
    security.mkdir()

    source = Path("scripts/audit-source")
    audit = scripts / "audit-source"
    shutil.copy2(source, audit)
    (security / "binary-assets.sha256").write_text(
        "# test binary allowlist\n",
        encoding="utf-8",
    )
    return audit


def _run(audit: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(audit)],
        cwd=audit.parent.parent,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_clean_minimal_tree_passes(tmp_path):
    result = _run(_audit_fixture(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "source tree audit passed" in result.stdout


def test_trojan_source_control_is_rejected(tmp_path):
    audit = _audit_fixture(tmp_path)
    (tmp_path / "probe.py").write_text(
        "# harmless text followed by a bidi control: \u202e\n",
        encoding="utf-8",
    )

    result = _run(audit)

    assert result.returncode == 1
    assert "Trojan Source control" in result.stderr


def test_unreviewed_binary_is_rejected(tmp_path):
    audit = _audit_fixture(tmp_path)
    (tmp_path / "opaque.bin").write_bytes(b"\x00\xffunreviewed")

    result = _run(audit)

    assert result.returncode == 1
    assert "unreviewed binary file" in result.stderr


def test_hash_allowlisted_binary_passes(tmp_path):
    audit = _audit_fixture(tmp_path)
    payload = b"\x00\xffreviewed"
    binary = tmp_path / "reviewed.bin"
    binary.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (tmp_path / "security" / "binary-assets.sha256").write_text(
        f"{digest}  reviewed.bin\n",
        encoding="utf-8",
    )

    result = _run(audit)

    assert result.returncode == 0, result.stdout + result.stderr
