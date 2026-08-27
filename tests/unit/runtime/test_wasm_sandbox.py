"""Wasmtime capability-sandbox tests."""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import pytest

from pentestagent.wasm_sandbox import (
    ComponentAllowlist,
    WasmSandboxError,
    WasmtimeSandbox,
)


def _sandbox(tmp_path: Path):
    component = tmp_path / "plugin.wasm"
    component.write_bytes(b"not-executed-in-unit-test")
    digest = hashlib.sha256(component.read_bytes()).hexdigest()
    allowlist = ComponentAllowlist(
        {digest: {"purpose": "parser", "name": "test-parser"}}
    )
    sandbox = WasmtimeSandbox(
        executable=Path("/run/current-system/sw/bin/wasmtime"),
        allowlist=allowlist,
        project_root=tmp_path,
    )
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    os.chmod(input_dir, 0o555)
    return sandbox, component, input_dir, output_dir


def test_command_has_limits_two_preopens_and_no_ambient_capabilities(tmp_path):
    sandbox, component, input_dir, output_dir = _sandbox(tmp_path)

    command = sandbox.command(component, input_dir, output_dir, ["report.json"])
    rendered = " ".join(command)

    assert "--wasm" in command
    assert "fuel=50000000" in rendered
    assert "epoch-interruption" in rendered
    assert "max-memory-size=134217728" in rendered
    assert f"{input_dir.resolve()}::/input" in command
    assert f"{output_dir.resolve()}::/output" in command
    assert "--env" not in command
    assert "--inherit-env" not in command
    assert "tcplisten" not in rendered
    assert "socket" not in rendered


def test_component_snapshot_is_hash_bound_and_write_sealed(tmp_path):
    sandbox, component, _input_dir, _output_dir = _sandbox(tmp_path)

    fd, digest = sandbox._snapshot_component(component)
    try:
        assert digest == hashlib.sha256(component.read_bytes()).hexdigest()
        assert os.pread(fd, 1024, 0) == component.read_bytes()
        with pytest.raises(OSError):
            os.pwrite(fd, b"replacement", 0)
    finally:
        os.close(fd)


@pytest.mark.asyncio
async def test_component_output_is_rejected_while_streaming():
    reader = asyncio.StreamReader()
    reader.feed_data(b"abcd")
    reader.feed_eof()

    with pytest.raises(WasmSandboxError, match="output exceeded"):
        await WasmtimeSandbox._read_bounded(reader, 3)


def test_writable_input_directory_is_rejected(tmp_path):
    sandbox, component, input_dir, output_dir = _sandbox(tmp_path)
    os.chmod(input_dir, 0o755)

    with pytest.raises(WasmSandboxError, match="read-only"):
        sandbox._validate_paths(component, input_dir, output_dir)


def test_writable_input_file_is_rejected(tmp_path):
    sandbox, component, input_dir, output_dir = _sandbox(tmp_path)
    os.chmod(input_dir, 0o755)
    item = input_dir / "input.bin"
    item.write_bytes(b"data")
    os.chmod(item, 0o600)
    os.chmod(input_dir, 0o555)

    with pytest.raises(WasmSandboxError, match="every input entry"):
        sandbox._validate_paths(component, input_dir, output_dir)


def test_output_symlink_is_rejected(tmp_path):
    sandbox, component, input_dir, output_dir = _sandbox(tmp_path)
    (output_dir / "escape").symlink_to("/tmp")

    with pytest.raises(WasmSandboxError, match="symlink"):
        sandbox._validate_paths(component, input_dir, output_dir)


def test_unknown_or_wrong_purpose_component_is_rejected():
    allowlist = ComponentAllowlist(
        {"a" * 64: {"purpose": "network-scanner"}}
    )

    with pytest.raises(WasmSandboxError, match="purpose"):
        allowlist.authorize("a" * 64)
    with pytest.raises(WasmSandboxError, match="not allowlisted"):
        allowlist.authorize("b" * 64)
